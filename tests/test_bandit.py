"""The bandit as ``revise``: what the posterior counts, that evidence beats the
incumbent, that a fan-out gets an independent draw per lane, and that the whole
thing drops into an outer run."""

from __future__ import annotations

import pytest
from shea.bandit import Bandit
from shea.loop import Outer
from shea.merkle_log import MerkleLog

SMALL = {"model": "small"}
BIG = {"model": "big"}


def row(config, ok):
    return {"kind": "trial", "config": config, "trial": {"ok": ok}}


def test_posterior_counts_per_arm_and_ignores_foreign_configs():
    bandit = Bandit([SMALL, BIG], seed=0)
    trials = [
        row(SMALL, False),
        row(SMALL, True),
        row(BIG, True),
        row({"model": "someone-elses-lane"}, True),
    ]
    assert bandit.posterior(trials) == [(1, 1), (1, 0)]


def test_no_trials_is_a_uniform_prior():
    assert Bandit([SMALL, BIG], seed=0).posterior([]) == [(0, 0), (0, 0)]


def test_evidence_beats_the_incumbent():
    """Twenty wins against twenty losses: Beta(21,1) vs Beta(1,21) barely
    overlap, so the losing incumbent gets revised away."""
    bandit = Bandit([SMALL, BIG], seed=0)
    trials = [row(SMALL, False)] * 20 + [row(BIG, True)] * 20
    assert bandit(trials, SMALL) == BIG
    assert bandit(trials, BIG) is None  # already on the best arm — no revision


def test_fan_out_draws_independently_per_lane():
    """The screenshot's shape: one outer, several lanes, one sample each. With
    no evidence the draws are uniform, so a batch is a spread, not a stampede."""
    bandit = Bandit([SMALL, BIG], seed=0)
    lanes = [bandit.pick([]) for _ in range(20)]
    assert SMALL in lanes and BIG in lanes


def test_custom_reward_reads_the_inner_s_own_shape():
    scored = Bandit([SMALL, BIG], reward=lambda r: r["trial"]["score"] > 0.5, seed=0)
    trials = [{"kind": "trial", "config": BIG, "trial": {"score": 0.9}}]
    assert scored.posterior(trials) == [(0, 0), (1, 0)]


def test_empty_arm_set_is_refused():
    with pytest.raises(ValueError):
        Bandit([])


class OnlyBigWorks:
    def run(self, goal, config):
        return {"ok": config == BIG}


def test_bandit_drives_an_outer_run_to_complete(tmp_path):
    log = MerkleLog(tmp_path)
    outer = Outer(
        inner=OnlyBigWorks(),
        stop=lambda trials: "complete" if trials[-1]["trial"]["ok"] else "continue",
        revise=Bandit([SMALL, BIG], seed=0),
        max_rounds=12,
    )

    assert outer.run("find the arm that works", SMALL, log) == "complete"

    rows = [p for _, p in log][::-1]  # oldest first
    assert rows[0] == {
        "kind": "trial",
        "round": 1,
        "config": SMALL,
        "trial": {"ok": False},
    }
    assert rows[-1]["config"] == BIG  # the winning round ran on the revised arm
    assert {r["kind"] for r in rows} == {"trial", "revision"}
    log.verify()
