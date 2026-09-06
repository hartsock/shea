"""Noticing that the harness, not the attempt, is what is wrong.

Lee's rule is the whole point of the outer loop: *an inner failure means the
attempt was wrong; a whole row plateauing means the harness was wrong.* Only
the first half was reachable — an inner reports `ok: False` and the outer
revises. The second half had no signal, and `blocked` was reachable only by
running out of rounds, which is a timeout wearing a verdict's clothes.

A plateau is the outcome not moving across a window of rounds. That is all it
is. Whether the config changed over the window says what to *blame*, not
whether there is a plateau — both readings indict the harness:

- the config never moved, so the harness is not trying anything new (a bandit
  whose arm set is exhausted keeps sampling the incumbent);
- the config moved every round and nothing changed, so what it is trying does
  not help.

The window rows are the attribution: whoever handles `blocked` has
`trials[-window:]` and every config in it, each already content-addressed by
the log.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from shea.loop import Trial, Verdict


def reported_ok(row: Trial) -> bool:
    """Default outcome: the inner reported success. Mirrors `shea.bandit`'s
    reader; the two collapse into one once both have landed."""
    return bool(row.get("trial", {}).get("ok"))


def plateaued(
    trials: Sequence[Trial],
    *,
    window: int = 3,
    outcome: Callable[[Trial], object] = reported_ok,
) -> bool:
    """True when the last `window` rounds all produced the same outcome.

    `outcome` need not be a boolean — return a score and a plateau is a score
    that has stopped moving. It must be hashable.
    """
    if window < 2:
        raise ValueError(f"a window of {window} always plateaus; use 2 or more")
    if len(trials) < window:
        return False
    return len({outcome(row) for row in trials[-window:]}) == 1


def blocked_on_plateau(
    stop: Callable[[Sequence[Trial]], Verdict],
    *,
    window: int = 3,
    outcome: Callable[[Trial], object] = reported_ok,
) -> Callable[[Sequence[Trial]], Verdict]:
    """Wrap a Goal Mode predicate so a plateaued row returns `blocked`.

    Only `continue` is overridden: a `complete` run has met the goal whether or
    not the last few rounds looked alike, and an already-`blocked` verdict is
    left as the inner predicate reported it.
    """

    def stop_on_plateau(trials: Sequence[Trial]) -> Verdict:
        verdict = stop(trials)
        if verdict == "continue" and plateaued(trials, window=window, outcome=outcome):
            return "blocked"
        return verdict

    return stop_on_plateau
