# shea — Agent Instructions

`CLAUDE.md` is a symlink to this file. Workspace-wide rules in
`~/workspaces/CLAUDE.md` apply on top; the Craft Register
(`steward-charter/docs/CRAFT.md`) wins on any doctrinal drift.

## What this repo is

Shawn Hartsock's Experimental Agent: a Python host over newt-agent's crates
(PyO3) and CLI/TUI components. Read `README.md` for the charter and the six
goals. It is also a live test of newt's `NEWT_BRAND_*` rebranding seam.

## Build + test

```bash
source ~/venv/bin/activate      # workspace rule: ~/venv for all Python work
pip install -e ".[dev]"
just install-hooks              # .githooks/ = commit-msg + pre-push
just check                      # black + ruff + pytest — the local CI mirror
```

`just check`, `.githooks/pre-push`, and `.github/workflows/ci.yml` must stay
in lock-step (CRAFT-14). Editing one means auditing the other two.

## Rules

- **Never push to `main`.** Branch → TDD → `just check` green → push → PR.
  Humans merge. Never `--no-verify`.
- **No Claude session URLs in commits or PR bodies.** `.githooks/commit-msg`
  blocks them. `Co-Authored-By:` attribution is fine.
- **One file per commit**, WHAT/WHY in the message. Author email is
  `hartsock@users.noreply.github.com`.
- **No dependency before it is imported.** `newt-agent-py` joins
  `pyproject.toml` the day a module imports it, pinned to the newt rev it was
  built from.
- **Reuse newt; do not re-implement it.** Before writing a tool, a store, an
  id, or a loop, check newt-agent (`newt-data`, `newt-eval`, `newt-tools`,
  `newt-core::agentic`) and the workspace's `content-addressable` crate. Run
  the `provenance-audit` skill before designing any persisted structure.
- **Composition roots are manifests** (CRAFT-03): `src/shea/__init__.py`
  holds no logic. New members get their own file.
- **Ambient authority, engineered for OpenShell.** Do not add OCAP plumbing.
- **Regression rule:** every bug fix lands with a test that failed first.
- **dgx1 is inference only.** Never clone, build, or run agents there.
- **Clean up:** one worktree per task, `git worktree remove` when done.
