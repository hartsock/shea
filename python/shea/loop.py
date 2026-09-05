"""The loops.

An ``Inner`` makes one attempt at a goal under a config and returns a trial
(a dag-cbor-representable dict). An ``Outer`` runs rounds: fire the
``before_round`` rails, run the inner, log the trial, fire ``after_round``,
ask the stopping predicate (Goal Mode: ``continue | complete | blocked``), and
between rounds ask ``revise`` for a new config — the meta-harness move. A
revision is logged as its own row, so a plateau is attributable to the
config that produced it.

The outer loop edits only ``config``, a plain dict. It never touches the
inner's code. Because every row goes through the Merkle log, a config must
be data: a callable in it fails at ``to_canonical_dagcbor`` — the rule biting
where it should.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Protocol

from shea.merkle_log import MerkleLog

Verdict = Literal["continue", "complete", "blocked"]
Config = dict[str, Any]
Trial = dict[str, Any]


class Inner(Protocol):
    def run(self, goal: str, config: Config) -> Trial: ...


@dataclass(frozen=True)
class Rail:
    """A capability attached at lifecycle hooks: ``(hooks, handler, priority)``
    plus the execution subjects it is visible to (``"*"`` = everyone)."""

    hooks: frozenset[str]
    handler: Callable[[dict], None]
    priority: int = 0
    visible_to: frozenset[str] = frozenset({"*"})

    def visible(self, subject: str) -> bool:
        return "*" in self.visible_to or subject in self.visible_to


@dataclass
class Outer:
    inner: Inner
    stop: Callable[[list[Trial]], Verdict]
    revise: Callable[[list[Trial], Config], Config | None] = lambda trials, cfg: None
    rails: Iterable[Rail] = ()
    max_rounds: int = 10
    subject: str = "outer"

    def _fire(self, hook: str, record: dict) -> None:
        # Lower priority number first; ties keep declaration order.
        for rail in sorted(
            (r for r in self.rails if hook in r.hooks and r.visible(self.subject)),
            key=lambda r: r.priority,
        ):
            rail.handler(record)

    def run(self, goal: str, config: Config, log: MerkleLog) -> Verdict:
        trials: list[Trial] = []
        for round_no in range(1, self.max_rounds + 1):
            self._fire(
                "before_round", {"round": round_no, "goal": goal, "config": config}
            )
            trial = self.inner.run(goal, config)
            row = {"kind": "trial", "round": round_no, "config": config, "trial": trial}
            log.append(row)
            trials.append(row)
            self._fire("after_round", row)
            verdict = self.stop(trials)
            if verdict != "continue":
                return verdict
            revised = self.revise(trials, config)
            if revised is not None and revised != config:
                log.append(
                    {
                        "kind": "revision",
                        "round": round_no,
                        "from": config,
                        "to": revised,
                    }
                )
                config = revised
        return "blocked"
