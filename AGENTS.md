# shea — Agent Instructions

`CLAUDE.md` is a symlink to this file. Workspace-wide rules in
`~/workspaces/CLAUDE.md` apply on top; the Craft Register
(`steward-charter/docs/CRAFT.md`) wins on any doctrinal drift.

## What this repo is

Shawn Hartsock's Experimental Agent: a Python host over newt-agent's crates
and newtui's components (PyO3, built from their `main`), plus newt's CLI/TUI.
Read `README.md` for the charter and the six goals. It is also a live test of
newt's `NEWT_BRAND_*` rebranding seam and of newt/newtui reusability.

## Layout

- `Cargo.toml` + `src/` — the `shea-native` PyO3 crate (`shea._native`).
  `src/lib.rs` is a composition root; members register themselves from their
  own file (`src/ui.rs`).
- `python/shea/` — the Python package. `__init__.py` holds no logic.
- `tests/` — pytest; `test_native.py` calls one thing per reused crate family.

## Build + test

```bash
source ~/venv/bin/activate      # workspace rule: ~/venv for all Python work
pip install pytest ruff black maturin
just install-hooks              # .githooks/ = commit-msg + pre-push
just build                      # maturin develop (first build: minutes)
just check                      # black + ruff + cargo fmt + clippy + pytest
```

`just check`, `.githooks/pre-push`, and `.github/workflows/ci.yml` must stay
in lock-step (CRAFT-14). Editing one means auditing the other two.

## Rules

- **Never push to `main`.** Branch → TDD → `just check` green → push → PR.
  Humans merge. Never `--no-verify`.
- **Session trailers ARE allowed here** (owner's decision, 2026-09-05) — a
  documented exception to the workspace-wide ban in `~/workspaces/CLAUDE.md`.
  shea is private and its subject is how agentic work gets produced, so the
  session that produced a commit is provenance, not plumbing. Keep
  `Co-Authored-By:` too. If shea goes public, revisit and scrub history first.
  This exception is shea's alone; other repos still expunge session links.
- **One file per commit**, WHAT/WHY in the message. Author email is
  `hartsock@users.noreply.github.com`.
- **Source, not shelves.** newt-agent and newtui are git dependencies on
  `main`; never swap them for crates.io / PyPI releases or a hand-pinned rev.
  `just update` ratchets `Cargo.lock` forward; commit the lock. Local sibling
  checkouts go through a git-ignored `.cargo/config.toml` `[patch]`.
- **No dependency before it is imported.** A crate or package joins the
  manifest the day a module uses it.
- **Everything is content-addressable.** Every data structure — persisted,
  transmitted, or merely handed between loops — SHALL derive its identity
  from its content through the `content-addressable` crate (`ContentId`,
  `RawContentId`, `MerkleNode`, `NodeStore`, `ClassifiedCid`). Over-use
  Merkle logs and Merkle trees on purpose: trial logs, harness revisions,
  Rail sets, rosters, reports, experience. A hand-rolled hash or canonical
  encoding is a defect. Run the `provenance-audit` skill before designing any
  structure. Where a cryptographic structure causes a problem, write it in
  `ROADMAP.md` → Findings instead of routing around it; that observation is a
  deliverable of the experiment.
- **Reuse newt; do not re-implement it.** Before writing a tool, a store, an
  id, or a loop, check newt-agent (`newt-data`, `newt-eval`, `newt-tools`,
  `newt-core::agentic`) and newtui.
- **Composition roots are manifests** (CRAFT-03): `src/lib.rs` and
  `python/shea/__init__.py` hold no logic. New members get their own file.
- **Ambient authority, engineered for OpenShell.** Do not add OCAP plumbing.
- **Regression rule:** every bug fix lands with a test that failed first.
- **dgx1 is inference only.** Never clone, build, or run agents there.
- **Clean up:** one worktree per task, `git worktree remove` when done;
  `target/` is disposable.
