# shea — Shawn Hartsock's Experimental Agent

![Shea logo](docs/logo/shea_logo_banner_large.png)

**Status:** chartered 2026-09-04 · private · v0.0.1 (newt and newtui assembled from source; the harness itself not yet begun)

`shea` is a Python host assembled from
[newt-agent](https://github.com/Gilamonster-Foundation/newt-agent),
[newtui](https://github.com/Gilamonster-Foundation/newtui), and their siblings
in the [Gilamonster Foundation](https://github.com/orgs/Gilamonster-Foundation/repositories).
It is not a fork of either. newt's crates and newtui's components are reached
from Python through PyO3 (`shea._native`, built here from their `main`
branches); newt's `newt-cli` / `newt-tui` are reused as-is. shea writes the
Python on top.

## What this variation of the agent is for

1. **Python based**, using Rust via PyO3 — the harness logic lives in Python,
   the heavy lifting in newt's and newtui's crates.
2. **Inner/outer harness** — a flexible harness-in-harness configuration,
   modeling a variant of Christina Lee's meta-harness for the Kimi K3 chip
   ([luoluo.ai, 2026-08-05](https://www.luoluo.ai/blog/kimi-k3)): an inner
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
   DataStore: CSV ingest, SQL query, summarize), reachable here as
   `shea._native.data`; shea starts from that.
6. **Fleets of inner and outer agents that interact.**

A second purpose runs alongside: **verifying that newt-agent and newtui reuse
in a configuration neither was built in** — a Python process, tracking their
current `main`, assembling its own selection of their parts.

## Safety and Security

**Authority:** shea uses **ambient authority**, not OCAP. Confinement is the
runtime's job: shea is engineered to run inside
[OpenShell](https://github.com/NVIDIA/OpenShell) (sandboxed agent runtime —
Landlock + seccomp + network namespaces, policy in OPA/Rego), so the harness
does not carry its own capability leash. The `--ocap` posture newt offers is
left switched off.

## Dependency policy: source, not shelves

newt-agent and newtui enter as **git dependencies on `main`** (`Cargo.toml`),
never as crates.io or PyPI releases — those lag `main` by weeks, and the point
is whether *current* newt and newtui reuse in a foreign host. `Cargo.lock`
records the exact commits a build used, so a build is reproducible;
`just update` ratchets the lock forward to current `main`.

To build against a local, uncommitted checkout, drop a patch into
`.cargo/config.toml` (git-ignored), one line per crate you want overridden:

```toml
[patch."https://github.com/Gilamonster-Foundation/newt-agent"]
newt-core = { path = "../newt-agent/newt-core" }
newt-data = { path = "../newt-agent/newt-data" }

[patch."https://github.com/Gilamonster-Foundation/newtui"]
newtui = { path = "../Gilamonster-Foundation/newtui" }
```

What `shea._native` assembles today: newt's `core`, `data`, `tools`,
`inference`, `coder`, `eval`, `acp_worker`, `mcp` modules (the same
`pyo3_module::register` hooks the umbrella `newt-agent-py` wheel stitches, but
selected here) and a `ui` module that runs newtui's exhaustive `Explorer`
in-process. `tests/test_native.py` calls one thing from each family.

## The rebranding test

This repo is in part a test of newt-agent's rebranding features. newt reads
five variables at runtime — `NEWT_BRAND_NAME`, `NEWT_BRAND_TAGLINE`,
`NEWT_BRAND_LOGO_DIR`, `NEWT_BRAND_LOGO_PREFIX`, `NEWT_BRAND_PLUGINS`
(newt-tui `src/brand.rs`; harness qualifier in newt-core
`src/build_info.rs`). `python/shea/brand.py` sets the first two and execs
`newt`.

Findings so far (newt 0.8.0, 2026-09-04):

- **Works:** the attribution harness qualifier. `shea identity` prints a
  trailer of the form `Co-authored-by: <model> (shea v0.8.0 …)`. The TUI
  splash and crawl header use the same seam.
- **Not covered by the seam:** the agent's commit *identity* (name and email
  stay `newt-agent`). A shea identity needs `~/.newt/agent-identity.toml`, or
  `newt identity set --name … --email …`.
- **Not yet exercised:** logo override (`LOGO_DIR`/`LOGO_PREFIX`) — shea now
  carries its own banner art, while newt still falls back to its own logo
  gracefully.

## Quick start

```bash
source ~/venv/bin/activate
pip install pytest ruff black maturin
just install-hooks
just build          # maturin develop — first build compiles newt from source
just check          # black + ruff + cargo fmt + clippy + pytest
shea identity       # newt, wearing the shea brand
shea                # the newt TUI, wearing the shea brand
```

`shea` needs a `newt` binary on `PATH`, built from the same checkout you are
tracking: `cargo install --path ~/workspaces/newt-agent/newt-cli`.

## Not yet

- **newt's TUI in-process.** `shea` still execs the `newt` binary for the TUI.
  newt-cli exposes `parse_with_help` and `dispatch` as a library, so an
  in-process `shea._native.run(argv)` is possible; its default features pull
  the embedded candle summarizer, so it waits for a reason.
- **Python-defined newtui components.** `ui.smoke` explores a Rust component.
  The bridge that lets newtui's Explorer walk a component written in Python is
  the next issue.
- **The harness, the DSL, the data-science tools, the fleet.** Goals 2–6 are
  the roadmap, one issue and one PR at a time.

## License

Apache-2.0
