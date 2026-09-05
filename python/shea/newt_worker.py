"""NewtWorker — the first real ``Inner``: one ``newt worker`` process per trial.

newt's worker is a small, bespoke JSON-RPC 2.0 server on stdio: one JSON
object per line, strictly sequential, four methods (``initialize``,
``new_session``, ``set_session_model`` — inert —, ``prompt``), no cancel, no
notifications. The ``prompt`` result is newt's ``TaskReply``:
``model_id, content, diff, empty_diff, diff_applied[, emission_shape,
raw_emission, metrics]``. ``empty_diff: true`` arrives as a *success*
envelope; classifying it as a failed trial is the caller's job, and this
class does it.

Launch facts that matter (newt 0.8.0, verified 2026-09-05):

- Always ``--config-dir <shea-owned dir>``: the worker resolves identity and
  backend before reading stdin, and a broken drop-in in the operator's
  ``~/.newt`` makes a plain ``newt worker`` exit 1. The operator key is
  minted inside the config dir; ``~/.newt`` is never touched.
- The model is pinned only by ``--backend-*`` flags; ``NEWT_DEFAULT_MODEL``
  and ``set_session_model`` are no-ops. The endpoint comes from an env var
  *named* in the config, never a literal, because the config is logged.
- Every inherited ``NEWT_*`` is dropped, so the logged config is the whole
  truth about how the worker ran. None is set back: ``NEWT_CODER`` in
  particular is read two incompatible ways by newt and breaks startup.
- ``cwd`` is the config dir, so newt's cwd-relative config walk-up finds
  nothing of the operator's.
- No server-side timeout; the host owns the deadline and kills the process.
- The worker's ``diff`` is unstaged and blind to untracked files, so shea
  captures its own (``git add -A -f && git diff --cached HEAD``) and scores
  on that.

Two hazards this module is built around. A trial is *data that gets logged*,
so the endpoint never reaches it: everything is scrubbed by value, because
the endpoint arrives inside JSON-RPC error text and newt's retry warnings,
not only in a known field. And the worker runs a model that may write
anywhere in the workspace, ``.git/`` included, so every git call here is
hardened the way newt's own git tool is.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

Config = dict[str, Any]

DEFAULTS: Config = {"coder": True, "timeout_s": 600, "backend": None}
"""``backend`` is ``None`` (newt's loopback Ollama fallback, honoring
``OLLAMA_HOST``) or ``{"name", "kind", "model", "endpoint_env"}`` where
``endpoint_env`` names the environment variable holding the endpoint."""

# One JSON-RPC line carries content + diff + raw_emission, so a single
# rewritten file can exceed asyncio's 64 KiB default and lose the trial.
STDOUT_LINE_LIMIT = 64 * 1024 * 1024

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Mirrors newt's own hardened_git: a model may write .git/config, and these
# keys execute commands on an ordinary `git add`.
_GIT_SAFE = [
    "--no-optional-locks",
    *("-c", "core.fsmonitor="),
    *("-c", "core.hooksPath=/dev/null"),
    *("-c", "core.pager=cat"),
    *("-c", "core.sshCommand=false"),
    *("-c", "core.askpass="),
    *("-c", "core.editor=false"),
    *("-c", "core.excludesFile=/dev/null"),
    *("-c", "diff.external="),
    *("-c", "protocol.ext.allow=never"),
]


class WorkerError(RuntimeError):
    pass


def _git(ws: Path, *args: str) -> str:
    """Run git in ``ws`` with nothing of the operator's environment or config,
    and with the repo-local keys that can execute commands neutralized."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/"),
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    proc = subprocess.run(  # noqa: PLW1510 — returncode is checked below, with git's stderr
        ["git", *_GIT_SAFE, *args],
        cwd=ws,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise WorkerError(
            f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def baseline(ws: Path) -> None:
    """Make ``ws`` a git repo with everything committed, so each trial diffs
    against a known base. Idempotent."""
    if not (ws / ".git").exists():
        _git(ws, "init", "-q", "-b", "main")
    _git(ws, "add", "-A", "-f")
    _git(
        ws,
        "-c",
        "user.email=shea@local",
        "-c",
        "user.name=shea",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "baseline",
    )


def reset(ws: Path) -> None:
    """Back to the baseline commit: every change dropped, tracked or not,
    ignored or not, whatever the index says.

    ponytail: does not restore `.git/` internals the model may have written
    (info/exclude, a corrupt index). `-f`/`-x` neutralize ignore-rule
    sabotage; a corrupted index surfaces as a WorkerError in the trial. Move
    the git dir outside the workspace if that stops being enough.
    """
    _git(ws, "reset", "-q", "--hard")
    _git(ws, "clean", "-qffdx")


def workspace_diff(ws: Path) -> str:
    """What actually changed, new and ignored files included (the worker's own
    diff is unstaged-only). Leaves the index as it found it."""
    _git(ws, "add", "-A", "-f")
    try:
        return _git(
            ws,
            "diff",
            "--cached",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
            "HEAD",
        )
    finally:
        _git(ws, "reset", "-q")


def _scrub(value: Any, secrets: list[str]) -> Any:
    """Replace every endpoint and hostname anywhere in the trial.

    By value, not by field: the endpoint reaches a trial through JSON-RPC
    error text and newt's retry warnings as readily as through
    ``metrics.endpoint``.
    """
    if not secrets:
        return value
    text = json.dumps(value)
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, "<scrubbed>")
    return json.loads(text)


@dataclass
class NewtWorker:
    """``run(goal, config)`` spawns a worker, drives one goal, returns the trial."""

    workspace: Path
    config_dir: Path
    bin: str | None = None
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace).resolve()
        self.config_dir = Path(self.config_dir).resolve()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.bin = self.bin or os.environ.get("NEWT_WORKER_BIN") or shutil.which("newt")
        if not self.bin:
            raise WorkerError(
                "no `newt` binary: set NEWT_WORKER_BIN or put newt on PATH"
            )
        if not os.access(self.bin, os.X_OK):
            raise WorkerError(f"newt binary is not executable: {self.bin}")

    def run(self, goal: str, config: Config) -> dict:
        return asyncio.run(self._run(goal, {**DEFAULTS, **config}))

    def _endpoint(self, config: Config) -> str | None:
        if b := config["backend"]:
            endpoint = os.environ.get(b["endpoint_env"])
            if not endpoint:
                raise WorkerError(
                    f"backend {b['name']!r}: env var {b['endpoint_env']} is unset"
                )
            return endpoint
        return self.env.get("OLLAMA_HOST") or os.environ.get("OLLAMA_HOST")

    def _secrets(self, endpoint: str | None) -> list[str]:
        """The endpoint strings shea itself supplied, plus their bare hosts —
        newt's error text quotes both forms."""
        out = []
        for value in {
            endpoint,
            self.env.get("OLLAMA_HOST"),
            os.environ.get("OLLAMA_HOST"),
        }:
            if not value:
                continue
            out.append(value)
            if host := urlsplit(value).hostname:
                out.append(host)
        return sorted(set(out))

    def _argv(self, config: Config) -> list[str]:
        argv = [self.bin, "--config-dir", str(self.config_dir), "worker"]
        if config["coder"]:
            argv.append("--coder")
        if b := config["backend"]:
            argv += [
                *("--backend-name", b["name"]),
                *("--backend-kind", b["kind"]),
                *("--backend-model", b["model"]),
                *("--backend-endpoint", self._endpoint(config)),
            ]
        return argv

    def _env(self, config: Config) -> dict[str, str]:
        # Drop every inherited NEWT_* — an exported NEWT_CODER or NEWT_PROVIDER
        # would silently override the config this trial logs.
        env = {k: v for k, v in os.environ.items() if not k.startswith("NEWT_")}
        env.update({"NEWT_EPHEMERAL": "1", "RUST_LOG": "warn"})
        # NEWT_CODER is deliberately NOT set: clap's `--coder` reads it as a
        # bool value (`true`/`false`) while the server reads `== "1"`, so the
        # documented `NEWT_CODER=1` makes the worker exit 2. The `--coder`
        # flag and the `coder` session param carry the choice instead.
        env.update(self.env)
        return env

    async def _run(self, goal: str, config: Config) -> dict:
        t0 = time.monotonic()
        error: str | None = None
        reply: dict = {}
        diff = ""
        prompt_ms = 0.0
        exit_code: int | None = None
        stderr = ""
        secrets: list[str] = []

        try:
            endpoint = self._endpoint(config)
            secrets = self._secrets(endpoint)
            argv = self._argv(config)
            reset(self.workspace)
        except WorkerError as e:
            # No process was started: still a trial, still a logged row.
            return _scrub(
                {
                    "goal": goal,
                    "ok": False,
                    "error": str(e),
                    "reply": {},
                    "diff": "",
                    "timing_ms": {
                        "total": round((time.monotonic() - t0) * 1000),
                        "prompt": 0,
                    },
                    "exit_code": None,
                    "stderr_tail": "",
                },
                secrets,
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config_dir,
                env=self._env(config),
                limit=STDOUT_LINE_LIMIT,
            )
        except OSError as e:
            return _scrub(
                {
                    "goal": goal,
                    "ok": False,
                    "error": f"spawn failed: {e}",
                    "reply": {},
                    "diff": "",
                    "timing_ms": {
                        "total": round((time.monotonic() - t0) * 1000),
                        "prompt": 0,
                    },
                    "exit_code": None,
                    "stderr_tail": "",
                },
                secrets,
            )

        stderr_task = asyncio.create_task(proc.stderr.read())
        next_id = 0

        async def call(method: str, params: dict) -> Any:
            nonlocal next_id
            next_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": method,
                "params": params,
            }
            proc.stdin.write((json.dumps(request) + "\n").encode())
            await proc.stdin.drain()
            try:
                line = await proc.stdout.readline()
            except ValueError as e:  # line over STDOUT_LINE_LIMIT
                raise WorkerError(f"{method}: reply line too long: {e}") from e
            if not line:
                raise WorkerError(f"worker exited before answering {method}")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                raise WorkerError(f"{method}: reply is not JSON: {e}") from e
            if msg.get("error"):
                raise WorkerError(f"{method}: {msg['error']}")
            if msg.get("id") != next_id:
                raise WorkerError(f"{method}: reply id {msg.get('id')!r} != {next_id}")
            return msg["result"]

        async def conversation() -> tuple[dict, float]:
            await call("initialize", {})
            session = await call(
                "new_session",
                {"workspace_path": str(self.workspace), "coder": bool(config["coder"])},
            )
            started = time.monotonic()
            answer = await call(
                "prompt", {"session_id": session["session_id"], "prompt": goal}
            )
            return answer, (time.monotonic() - started) * 1000

        try:
            reply, prompt_ms = await asyncio.wait_for(
                conversation(), timeout=config["timeout_s"]
            )
        except asyncio.TimeoutError:
            error = f"timeout after {config['timeout_s']}s"
        except (WorkerError, OSError) as e:
            error = str(e)
        finally:
            if proc.returncode is None:
                if error is None:
                    proc.stdin.close()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        proc.kill()
                else:
                    proc.kill()
                await proc.wait()
            exit_code = proc.returncode
            stderr = _ANSI.sub("", (await stderr_task).decode(errors="replace"))

        try:
            diff = workspace_diff(self.workspace)
        except WorkerError as e:
            error = error or f"diff failed: {e}"

        return _scrub(
            {
                "goal": goal,
                "ok": error is None and bool(diff.strip()),
                "error": error,
                "reply": reply,
                "diff": diff,
                "timing_ms": {
                    "total": round((time.monotonic() - t0) * 1000),
                    "prompt": round(prompt_ms),
                },
                "exit_code": exit_code,
                "stderr_tail": stderr[-2000:],
            },
            secrets,
        )
