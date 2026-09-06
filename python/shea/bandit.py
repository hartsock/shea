"""``revise`` as a fitted policy instead of a hand-written ladder.

Track A's open question is how the outer loop notices a flat row and blames
the harness rather than the attempt. Today ``revise`` walks a hardcoded model
ladder, which is a counter wearing a policy's clothes: it moves whether or not
the move helps, and nothing it does is attributable to evidence.

This is the smallest honest replacement — Thompson sampling over a fixed arm
set. One ``Beta(wins + 1, losses + 1)`` posterior per arm, sampled once per
decision, highest sample takes the lane.

A bandit rather than a regression because a bandit is honest about small ``N``
by construction: with three rows every posterior is wide, so it explores; it
narrows only as the log fills. A decision tree over three rows fits noise and
reports a confident number for it. Reach for something fitted when the log
holds hundreds of rows and the arm set has stopped being enumerable.

Arms are matched by value. Nothing here is persisted or transmitted — the rows
it reads were content-addressed by the log on the way in, and an in-memory
lookup key is not a data structure the first principle governs.

Two entry points over the same posterior:

- ``pick(trials)`` — an arm for one lane. A fan-out outer calls it once per
  lane and the independent samples give the parallel spread for free.
- ``__call__(trials, config)`` — the ``Outer.revise`` adapter for a single
  sequential lane, returning ``None`` when the sample lands on the incumbent.

``None`` is *not* a plateau claim. A sample landing on the incumbent is one
draw, not a flat row; real plateau detection is still Track A's to write.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from shea.loop import Config, Trial


def reported_ok(row: Trial) -> bool:
    """Default reward: the inner reported success (``NewtWorker``'s shape)."""
    return bool(row.get("trial", {}).get("ok"))


class Bandit:
    """Thompson sampling over ``arms``, fit from the outer loop's trial rows.

    ``reward`` reads one logged row and says whether that trial won; the
    default reads ``row["trial"]["ok"]``. ``seed`` fixes the sampling for
    tests and for replay.
    """

    def __init__(
        self,
        arms: Sequence[Config],
        *,
        reward: Callable[[Trial], bool] = reported_ok,
        seed: int | None = None,
    ) -> None:
        if not arms:
            raise ValueError("a bandit needs at least one arm")
        self.arms = list(arms)
        self.reward = reward
        self._rng = random.Random(seed)

    def posterior(self, trials: Sequence[Trial]) -> list[tuple[int, int]]:
        """``(wins, losses)`` per arm — the outer's table column.

        Rows whose config is not one of ``arms`` contribute nothing, so a log
        carrying other lanes' work can be handed over whole.
        """
        counts = [[0, 0] for _ in self.arms]
        for row in trials:
            i = self._index(row.get("config"))
            if i is not None:
                counts[i][0 if self.reward(row) else 1] += 1
        return [(w, x) for w, x in counts]

    def pick(self, trials: Sequence[Trial]) -> Config:
        """One arm, sampled from the posterior. Call once per lane."""
        draws = [self._rng.betavariate(w + 1, x + 1) for w, x in self.posterior(trials)]
        return self.arms[draws.index(max(draws))]

    def __call__(self, trials: Sequence[Trial], config: Config) -> Config | None:
        arm = self.pick(trials)
        return None if arm == config else arm

    def _index(self, config: Config | None) -> int | None:
        return next((i for i, a in enumerate(self.arms) if a == config), None)
