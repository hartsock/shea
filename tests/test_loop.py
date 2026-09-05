"""One outer run end to end: rounds, a revision, rails in order, a verdict,
and every row of it in the log."""

from __future__ import annotations

import pytest
from shea.loop import Outer, Rail
from shea.merkle_log import MerkleLog


class Ramp:
    """An inner whose score is the config's temperature — so only a revision
    can move the outcome."""

    def run(self, goal, config):
        return {"score": config["temperature"]}


def stop(trials):
    return "complete" if trials[-1]["trial"]["score"] >= 0.9 else "continue"


def warmer(trials, cfg):
    return {**cfg, "temperature": round(cfg["temperature"] + 0.4, 1)}


def test_outer_revises_config_until_complete_and_logs_every_row(tmp_path):
    log = MerkleLog(tmp_path)
    fired = []
    rails = [
        Rail(
            frozenset({"after_round"}),
            lambda r: fired.append(("late", r["round"])),
            priority=9,
        ),
        Rail(
            frozenset({"after_round"}),
            lambda r: fired.append(("early", r["round"])),
            priority=1,
        ),
        Rail(
            frozenset({"after_round"}),
            lambda r: fired.append(("hidden", r["round"])),
            visible_to=frozenset({"crew"}),
        ),
    ]
    outer = Outer(inner=Ramp(), stop=stop, revise=warmer, rails=rails, max_rounds=5)

    assert outer.run("get warm", {"temperature": 0.1}, log) == "complete"

    rows = [p for _, p in log][::-1]  # oldest first
    assert [r["kind"] for r in rows] == [
        "trial",
        "revision",
        "trial",
        "revision",
        "trial",
    ]
    assert rows[-1]["trial"]["score"] == 0.9
    assert rows[1] == {
        "kind": "revision",
        "round": 1,
        "from": {"temperature": 0.1},
        "to": {"temperature": 0.5},
    }
    assert fired == [
        ("early", 1),
        ("late", 1),
        ("early", 2),
        ("late", 2),
        ("early", 3),
        ("late", 3),
    ]


def test_outer_blocks_at_the_round_cap(tmp_path):
    outer = Outer(inner=Ramp(), stop=stop, max_rounds=2)  # no revise → never warms
    assert outer.run("stuck", {"temperature": 0.1}, MerkleLog(tmp_path)) == "blocked"


def test_config_must_be_data(tmp_path):
    outer = Outer(inner=Ramp(), stop=stop, max_rounds=1)
    with pytest.raises(TypeError):
        outer.run(
            "no code in config",
            {"temperature": 0.1, "hook": print},
            MerkleLog(tmp_path),
        )
