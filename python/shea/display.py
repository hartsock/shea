"""Optional display: the outer loop's rows rendered by herdr's own sidebar.

herdr is a bin-only crate — no ``src/lib.rs``, nothing to link against — so the
seam is its CLI, backed by a versioned socket API when polling stops being
enough. And it is a *view*, never a dependency: the Merkle log is the truth
whether or not anything renders it. An absent herdr means a shorter rail list,
not a branch in the loop, and a headless run is the normal case rather than a
degraded one.

Nothing here draws a table. ``herdr pane report-metadata`` pushes tokens and
herdr's own configured sidebar row renders them::

    [ui.sidebar.agents]
    rows = [["state_icon", "agent"], ["$model", "$backend"]]

``--ttl-ms`` expires the row, so a harness that dies leaves no stale lane
behind, and ``report-metadata`` deliberately does not take over
integration-owned lifecycle: the inner agent's own working/blocked/idle keeps
coming from herdr's detection. shea only adds columns.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterable

from shea.loop import Rail, Trial

#: herdr's own vocabulary. Its CLI refuses anything else.
STATES = frozenset({"idle", "working", "blocked", "done", "unknown"})

_SCALARS = (str, int, float, bool)


def metadata_argv(
    row: Trial,
    *,
    source: str = "shea",
    state: str = "working",
    ttl_ms: int = 600_000,
) -> list[str] | None:
    """The ``herdr pane report-metadata`` argv for one logged row, or ``None``
    when no pane owns the row — a headless lane has nothing to render.

    The pane is ``row["pane"]`` for a fan-out lane, else ``HERDR_PANE_ID``,
    which herdr injects into every pane it owns. Non-scalar config values are
    dropped: a nested dict in a sidebar cell is noise, not information.
    """
    if state not in STATES:
        raise ValueError(f"{state!r} is not one of herdr's states: {sorted(STATES)}")
    pane = row.get("pane") or os.environ.get("HERDR_PANE_ID")
    if not pane:
        return None
    argv = ["herdr", "pane", "report-metadata", str(pane), "--source", source]
    round_no = row.get("round")
    if round_no is not None:
        argv += ["--state-label", f"{state}=round-{round_no}"]
    for key, value in (row.get("config") or {}).items():
        if isinstance(value, _SCALARS):
            argv += ["--token", f"{key}={value}"]
    return argv + ["--ttl-ms", str(ttl_ms)]


def herdr_rail(
    *,
    source: str = "shea",
    state: str = "working",
    ttl_ms: int = 600_000,
    hooks: Iterable[str] = ("after_round",),
    priority: int = 50,
) -> Rail | None:
    """A ``Rail`` reporting each round to herdr, or ``None`` when herdr is not
    installed. Compose with ``rails=[r for r in (herdr_rail(),) if r]``.
    """
    if not shutil.which("herdr"):
        return None

    def report(row: Trial) -> None:
        argv = metadata_argv(row, source=source, state=state, ttl_ms=ttl_ms)
        if argv is None:
            return
        try:
            # A display failure never takes a trial down with it: a non-zero
            # exit is ignored, and herdr going away mid-run is an OSError.
            subprocess.run(argv, check=False, capture_output=True)
        except OSError:
            pass

    return Rail(frozenset(hooks), report, priority=priority)
