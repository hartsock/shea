# shea — Shawn Hartsock's Experimental Agent

**Status:** chartered 2026-09-04 · private · v0.0.1 (a rebranded `newt`, nothing more yet)

`shea` is a Python host assembled from the crates of
[newt-agent](https://github.com/Gilamonster-Foundation/newt-agent) and its
siblings in the [Gilamonster Foundation](https://github.com/orgs/Gilamonster-Foundation/repositories).
It is not a fork of newt. newt's `newt-cli` / `newt-tui` components are reused
as-is; newt's Rust crates are reached from Python through PyO3
(`newt-agent-py`). shea writes the Python on top.

## What this variation of the agent is for

1. **Python based**, using Rust via PyO3 — the harness logic lives in Python,
   the heavy lifting in newt's crates.
2. **Inner/outer harness** — a nested agentic harness in the shape of
   [Kimi K3's meta-harness](https://www.luoluo.ai/blog/kimi-k3): an inner
   loop attempts the work against a goal and logs trials; an outer loop watches
   the trials plateau and rewrites the harness itself — which reports it reads,
   which bottleneck it blames, which class of fix it proposes. *An inner failure
   means the attempt was wrong. A whole outer row plateauing means the harness
   was wrong.*
3. **Customizable agentic loops** — a Python DSL for expressing agent loops,
   not only coder loops.
4. **Customizable goals, intentions, evaluations, verifications** — the things
   a loop is judged by are the user's to write.
5. **Specialized tools for data science, reporting, and open-source EDA** —
   beyond merely coding. newt already ships `newt-data` (headless SQLite
   DataStore: CSV ingest, SQL query, summarize) with PyO3 bindings, and
   `newt-mcp-data` exposing it over MCP; shea starts from those.
6. **Fleets of inner and outer agents that interact.**

## Where it sits in the agent line

The line's capability ordering is `wyvern ≤ newt ≤ gilamonster`
(newt-agent `docs/decisions/agent_line_architecture.md`). shea is a peer of
gilamonster-agent in *how* it consumes newt (a host over pinned newt
components, rebranded through newt's runtime seam) and differs in *what* it
adds: Python, nested harnesses, and data-science tooling instead of a Rust
cockpit.

**Authority:** shea uses **ambient authority**, not OCAP. Confinement is the
runtime's job: shea is engineered to run inside
[OpenShell](https://github.com/NVIDIA/OpenShell) (sandboxed agent runtime —
Landlock + seccomp + network namespaces, policy in OPA/Rego), so the harness
does not carry its own capability leash. The `--ocap` posture newt offers is
left switched off.

## The rebranding test

This repo is in part a test of newt-agent's rebranding features. newt reads
five variables at runtime — `NEWT_BRAND_NAME`, `NEWT_BRAND_TAGLINE`,
`NEWT_BRAND_LOGO_DIR`, `NEWT_BRAND_LOGO_PREFIX`, `NEWT_BRAND_PLUGINS`
(newt-tui `src/brand.rs`; harness qualifier in newt-core
`src/build_info.rs`). `src/shea/brand.py` sets the first two and execs `newt`.

Findings so far (newt 0.8.0, 2026-09-04):

- **Works:** the attribution harness qualifier. `shea identity` prints a
  trailer of the form `Co-authored-by: <model> (shea v0.8.0 …)`. The TUI
  splash and crawl header use the same seam.
- **Not covered by the seam:** the agent's commit *identity* (name and email
  stay `newt-agent`). A shea identity needs `~/.newt/agent-identity.toml`, or
  `newt identity set --name … --email …`.
- **Not yet exercised:** logo override (`LOGO_DIR`/`LOGO_PREFIX`) — shea has
  no art; newt falls back to its own logo gracefully.

## Quick start

```bash
source ~/venv/bin/activate
pip install -e ".[dev]"
just install-hooks
just check          # black + ruff + pytest
shea identity       # newt, wearing the shea brand
shea                # the newt TUI, wearing the shea brand
```

`shea` needs a `newt` binary on `PATH`:
`cargo install --path ~/workspaces/newt-agent/newt-cli`.

## Not yet

- **PyO3 bindings.** `newt-agent-py` is not a dependency until shea first
  imports it. PyPI has 0.7.5; the 0.6.7 in `~/venv` is stale and does not
  import. When needed, build 0.8.0 from newt-agent: `maturin develop --release`.
- **The harness, the DSL, the data-science tools, the fleet.** Goals 2–6 are
  the roadmap, one issue and one PR at a time.

## License

Apache-2.0
