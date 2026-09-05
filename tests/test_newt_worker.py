"""NewtWorker against a canned Ollama: the whole wire path, offline, in ~10 ms.

The end-to-end tests need a `newt` binary; the unit tests do not, so the skip
is per-test. `NEWT_WORKER_BIN` counts as a binary, the way the class does.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from shea.merkle_log import MerkleLog
from shea.newt_worker import DEFAULTS, NewtWorker, WorkerError, baseline, reset

needs_newt = pytest.mark.skipif(
    not (os.environ.get("NEWT_WORKER_BIN") or shutil.which("newt")),
    reason="no newt binary (set NEWT_WORKER_BIN or put newt on PATH)",
)

NEW_BODY = "fn new() {}\n"
CANNED = f"FILE: lib.rs\n{NEW_BODY}END-FILE\n"  # newt-coder's whole-file emission
BIG_BODY = "".join(f"fn f{i}() {{}}\n" for i in range(6000))  # > 64 KiB one file


def _handler(content: str, delay: float = 0.0):
    class Ollama(BaseHTTPRequestHandler):
        """Answers any POST (the worker sends one POST /api/chat)."""

        def do_POST(self):
            if delay:
                time.sleep(delay)
            body = json.dumps(
                {
                    "model": "mock",
                    "message": {"role": "assistant", "content": content},
                    "done": True,
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

        def handle_one_request(self):
            try:  # the worker is killed on timeout; its broken pipe is expected
                super().handle_one_request()
            except OSError:
                self.close_connection = True

    return Ollama


def _serve(handler) -> tuple[str, HTTPServer]:
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_port}", srv


@pytest.fixture
def ollama():
    """Returns a factory: `ollama(content, delay=…)` -> url. Cleans up all."""
    servers = []

    def start(content: str, delay: float = 0.0) -> str:
        url, srv = _serve(_handler(content, delay))
        servers.append(srv)
        return url

    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


@pytest.fixture
def make_worker(tmp_path):
    def build(url: str, body: str = "fn old() {}\n") -> NewtWorker:
        ws = tmp_path / "ws"
        ws.mkdir(exist_ok=True)
        (ws / "lib.rs").write_text(body)
        baseline(ws)
        return NewtWorker(ws, tmp_path / "cfg", env={"OLLAMA_HOST": url})

    return build


@needs_newt
def test_one_trial_end_to_end_and_loggable(make_worker, ollama, tmp_path):
    worker = make_worker(ollama(CANNED))
    trial = worker.run("rename old to new", {"timeout_s": 60})
    assert trial["ok"], trial
    assert trial["reply"]["emission_shape"] == "whole_files"
    assert trial["diff"].startswith("diff --git a/lib.rs b/lib.rs")
    assert "+fn new() {}" in trial["diff"]
    assert "127.0.0.1" not in json.dumps(trial), "endpoint leaked into the trial"
    MerkleLog(tmp_path / "log").append(trial)  # dag-cbor clean, or this raises


@needs_newt
def test_each_trial_starts_from_the_baseline(make_worker, ollama):
    worker = make_worker(ollama(CANNED))
    first = worker.run("rename old to new", {"timeout_s": 60})
    # State the worker never produces: an untracked file, an ignored file, and
    # a mangled tracked one. Only a real reset clears all three.
    (worker.workspace / "junk.rs").write_text("fn junk() {}\n")
    (worker.workspace / ".gitignore").write_text("*.log\n")
    (worker.workspace / "noise.log").write_text("noise\n")
    (worker.workspace / "lib.rs").write_text("garbage\n")
    second = worker.run("rename old to new", {"timeout_s": 60})
    assert first["diff"] == second["diff"]
    assert not (worker.workspace / "junk.rs").exists()
    assert not (worker.workspace / "noise.log").exists()
    assert (worker.workspace / "lib.rs").read_text().rstrip("\n") == NEW_BODY.rstrip(
        "\n"
    )


@needs_newt
def test_empty_diff_is_a_failed_trial(make_worker, ollama):
    """The flat path gets a whole-file emission it cannot apply as a patch, so
    the worker returns a *success* envelope with an empty diff. That is a
    failed trial, and no `--coder` reaches the argv."""
    worker = make_worker(ollama(CANNED))
    trial = worker.run("rename old to new", {"timeout_s": 60, "coder": False})
    assert trial["error"] is None
    assert trial["ok"] is False
    assert trial["diff"] == ""
    assert "--coder" not in worker._argv({**DEFAULTS, "coder": False})


@needs_newt
def test_reply_larger_than_the_asyncio_default_limit(make_worker, ollama):
    """One rewritten file of ~80 KB makes the single JSON-RPC reply line exceed
    asyncio's 64 KiB default — which used to lose the trial entirely."""
    worker = make_worker(ollama(f"FILE: lib.rs\n{BIG_BODY}END-FILE\n"))
    trial = worker.run("write many functions", {"timeout_s": 60})
    assert trial["ok"], trial["error"]
    assert "fn f5999() {}" in trial["diff"]


@needs_newt
def test_timeout_kills_the_worker_and_still_returns_a_trial(
    make_worker, ollama, tmp_path
):
    worker = make_worker(ollama(CANNED, delay=5))
    trial = worker.run("too slow", {"timeout_s": 1})
    assert trial["error"].startswith("timeout after 1s")
    assert trial["ok"] is False
    assert trial["exit_code"] is not None, "worker was left running"
    MerkleLog(tmp_path / "log").append(trial)


@needs_newt
def test_endpoint_never_reaches_the_trial_on_the_failure_path(make_worker, tmp_path):
    """An unreachable backend puts the endpoint in newt's JSON-RPC error text
    and its retry warnings. Neither may reach the log."""
    worker = make_worker("http://127.0.0.1:1")
    worker.env.update({"NEWT_HTTP_MAX_RETRIES": "0", "NEWT_HTTP_BACKOFF_BASE_MS": "1"})
    trial = worker.run("unreachable", {"timeout_s": 120})
    assert trial["ok"] is False
    assert trial["error"], "expected the backend failure to be reported"
    blob = json.dumps(trial)
    assert "127.0.0.1:1" not in blob
    assert "<scrubbed>" in blob
    MerkleLog(tmp_path / "log").append(trial)


@needs_newt
def test_unset_backend_env_var_is_a_trial_not_an_exception(
    make_worker, ollama, monkeypatch
):
    worker = make_worker(ollama(CANNED))
    monkeypatch.delenv("SHEA_TEST_ENDPOINT", raising=False)
    backend = {
        "name": "x",
        "kind": "ollama",
        "model": "m",
        "endpoint_env": "SHEA_TEST_ENDPOINT",
    }
    trial = worker.run("goal", {"backend": backend})
    assert trial["ok"] is False
    assert "SHEA_TEST_ENDPOINT is unset" in trial["error"]
    assert trial["exit_code"] is None


def test_missing_binary_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("NEWT_WORKER_BIN", raising=False)
    with pytest.raises(WorkerError, match="no `newt` binary"):
        NewtWorker(tmp_path, tmp_path / "cfg")


def test_non_executable_binary_is_a_clear_error(tmp_path, monkeypatch):
    fake = tmp_path / "newt"
    fake.write_text("#!/bin/sh\n")  # present, not executable
    monkeypatch.setenv("NEWT_WORKER_BIN", str(fake))
    with pytest.raises(WorkerError, match="not executable"):
        NewtWorker(tmp_path, tmp_path / "cfg")


def test_reset_survives_a_baseline_with_no_tracked_files(tmp_path):
    ws = tmp_path / "empty"
    ws.mkdir()
    baseline(ws)  # nothing to track
    (ws / "made.rs").write_text("fn made() {}\n")
    reset(ws)
    assert not (ws / "made.rs").exists()


def test_git_calls_ignore_repo_local_config_that_would_run_commands(tmp_path):
    """A model can write .git/config; shea's own git must not execute it."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "lib.rs").write_text("fn old() {}\n")
    baseline(ws)
    (ws / ".git" / "config").open("a").write(
        f'\n[core]\n\tfsmonitor = "sh -c \'touch {ws / "PWNED"}\'"\n'
    )
    (ws / "lib.rs").write_text("fn new() {}\n")
    from shea.newt_worker import workspace_diff

    assert "+fn new() {}" in workspace_diff(ws)
    assert not (ws / "PWNED").exists(), "repo-local git config executed"


def test_scrub_replaces_the_endpoint_wherever_it_appears(tmp_path):
    worker = NewtWorker(
        tmp_path,
        tmp_path / "cfg",
        bin="/bin/sh",
        env={"OLLAMA_HOST": "http://h.invalid:9/"},
    )
    from shea.newt_worker import _scrub

    trial = {
        "error": "prompt: sending request for url (http://h.invalid:9/api/chat)",
        "stderr_tail": "WARN retrying error=connect to h.invalid:9 failed",
        "reply": {"metrics": {"endpoint": "http://h.invalid:9/"}},
    }
    clean = json.dumps(_scrub(trial, worker._secrets("http://h.invalid:9/")))
    assert "h.invalid" not in clean
    assert clean.count("<scrubbed>") >= 3
