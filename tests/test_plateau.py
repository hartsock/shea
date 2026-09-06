"""Plateau detection: what counts as a flat row, and that only `continue` is
overridden by it."""

from __future__ import annotations

import pytest
from shea.loop import Outer
from shea.merkle_log import MerkleLog
from shea.plateau import blocked_on_plateau, plateaued


def row(ok, config=None):
    return {"kind": "trial", "config": config or {}, "trial": {"ok": ok}}


def test_a_history_shorter_than_the_window_never_plateaus():
    assert plateaued([row(False), row(False)]) is False


def test_the_same_outcome_across_the_window_is_a_plateau():
    assert plateaued([row(False)] * 3) is True


def test_a_plateau_does_not_care_whether_the_config_moved():
    """Both readings indict the harness: not trying anything new, and trying
    things that do not help."""
    moved = [row(False, {"model": m}) for m in ("a", "b", "c")]
    assert plateaued(moved) is True


def test_one_different_outcome_in_the_window_breaks_it():
    assert plateaued([row(False), row(True), row(False)]) is False


def test_only_the_window_counts():
    """Variety older than the window does not rescue a flat tail."""
    assert plateaued([row(True), row(False), row(False), row(False)]) is True


def test_a_score_that_stopped_moving_is_a_plateau():
    trials = [{"trial": {"score": 0.4}} for _ in range(3)]
    assert plateaued(trials, outcome=lambda r: r["trial"]["score"]) is True
    trials[-1]["trial"]["score"] = 0.5
    assert plateaued(trials, outcome=lambda r: r["trial"]["score"]) is False


def test_a_window_of_one_is_refused():
    with pytest.raises(ValueError):
        plateaued([row(False)], window=1)


def test_the_wrapper_turns_continue_into_blocked():
    stop = blocked_on_plateau(lambda trials: "continue")
    assert stop([row(False)] * 2) == "continue"  # not yet a window
    assert stop([row(False)] * 3) == "blocked"


def test_the_wrapper_never_overrides_a_win():
    """Three identical successes are a met goal, not a flat row."""
    stop = blocked_on_plateau(lambda trials: "complete")
    assert stop([row(True)] * 3) == "complete"


def test_the_wrapper_leaves_an_inner_blocked_alone():
    stop = blocked_on_plateau(lambda trials: "blocked")
    assert stop([row(False), row(True)]) == "blocked"


class NeverWorks:
    def run(self, goal, config):
        return {"ok": False}


def test_an_outer_run_blocks_on_the_plateau_not_the_round_cap(tmp_path):
    log = MerkleLog(tmp_path)
    outer = Outer(
        inner=NeverWorks(),
        stop=blocked_on_plateau(lambda trials: "continue"),
        revise=lambda trials, cfg: {"attempt": len(trials)},
        max_rounds=50,
    )

    assert outer.run("impossible", {"attempt": 0}, log) == "blocked"

    rounds = [p["round"] for _, p in log if p["kind"] == "trial"][::-1]
    assert rounds == [1, 2, 3]  # blocked at the window, nowhere near the cap
