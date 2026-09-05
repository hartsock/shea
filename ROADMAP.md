# shea roadmap

Loose and experimental, on purpose. Tracks, not phases; no dates. Each track
names what exists in newt or newtui to reuse, the first slice worth cutting,
and the questions it is meant to answer. One issue, one PR, and the lock
ratchets forward on `main` of both upstreams.

## The frame

Two references, two axes:

- **openJiuwen** (arXiv 2608.27969, 2026-08-28; Python, Apache-2.0):
  an *Inner Loop* is one ReAct run — build the model-visible context, invoke
  the fixed policy, run tool calls, record observations, until an answer or a
  step cap. One inner run is one *Outer Loop* round; after each round a Goal
  Mode evaluator returns `continue | complete | blocked` under resource caps.
  Capabilities attach as **Rails**: `(hooks ⊆ {invoke, call, task}, handler,
  priority)` with **visibility gating** per execution subject. Delegated
  sub-agents and swarm flows reuse the same loops with different Rails
  visible. The outer loop may change framework-controlled state between
  rounds — context construction, the stopping predicate, injected
  diagnostics, an experience store — but never the policy.
- **Christina Lee's meta-harness** (luoluo.ai, 2026-08-05): the outer loop
  rewrites the *harness* when a whole row of inner attempts plateaus — which
  reports it reads, which bottleneck it blames, which class of fix it
  proposes. *An inner failure means the attempt was wrong. A plateaued row
  means the harness was wrong.*

shea explores Lee's move with openJiuwen's mechanics: **the outer loop's edit
target is the inner loop's declared configuration** — Rail set and
priorities, tool visibility, context budget, stopping predicate, sub-agent
roster. Never the inner loop's code. Every revision is logged as a row so a
plateau is attributable to the harness version that produced it.

Design rules that fall out of that:

1. The inner loop is a replaceable black box behind a wire contract.
2. The outer loop edits a typed surface, and every edit is a logged trial.
3. Task-level Rails first (before-round, after-round). Call-level Rails only
   when a Rail needs to be inside the loop.
4. The DSL is plain Python objects composed together. No string language,
   no parser.
5. **Everything is content-addressable.** Not just persisted rows: every
   data structure shea defines derives its identity from its content through
   the `content-addressable` crate, and Merkle logs and trees are over-used
   on purpose — trials, harness revisions, Rail sets, rosters, reports,
   experience. Traceability is forced by construction. Where that causes a
   problem, it goes in Findings below, not around.

## Done

- [x] `shea._native`: newt-agent's PyO3 modules and a newtui bridge, built
      from both repos' `main` (git deps; `Cargo.lock` is the ratchet).
- [x] `shea` = `newt` wearing the brand through the `NEWT_BRAND_*` seam.
- [x] Rebrand findings recorded (see "Upstream" below).
- [x] `shea.merkle_log.MerkleLog`: Track A's log — crate-minted Merkle nodes
      on disk, verified on read, replayable from `HEAD`.
- [x] `shea.loop`: `Inner` protocol, `Rail` (hooks, priority, visibility),
      `Outer` with Goal Mode stop and the `revise` hook; every round and
      revision a log row. Proven with a fake inner.
- [x] `shea.newt_worker.NewtWorker`: the first real inner — one `newt
      worker` process per trial over newt's line-delimited JSON-RPC, the
      workspace reset to a baseline before each trial, shea's own diff as the
      verdict, the trial dag-cbor clean and endpoint-scrubbed for the log.
      Offline test against a canned Ollama in ~10 ms; skips without `newt`.
      Hardened by a 5-lens adversarial review (23 findings applied): a
      64 KiB asyncio line limit that silently lost large trials, endpoint
      leaks through JSON-RPC error text and retry warnings, four exception
      paths that aborted the outer loop instead of logging a failed trial,
      a `reset` that missed ignored files and restored from the index, and
      git calls that would execute a model-written `.git/config`.

## Track A — the loops (`shea.loop`)

**Reuse:** `newt worker` (newt-acp-worker) — headless, speaks the Agent
Client Protocol over stdio, edits files, returns a `TaskReply` and a diff.
newt-eval's Python docs already say to drive it with
`asyncio.create_subprocess_exec`. `shea._native.acp_worker` has `TaskReply`,
`Session`, `capture_diff`, `is_empty_diff`.

**First slice** (done; see above). **Next:**

- A live run: `Outer` + `NewtWorker` against a real backend (local Ollama
  works today; the dgx1 router path is declared but unexercised through the
  worker), with the config's `backend` as the first revisable knob —
  `{"name", "kind", "model", "endpoint_env"}`, the endpoint by env var name
  only. A model change is a new process, which is fine: one process per
  trial already.
- Goal Mode over real trials: `ok` + newt-eval evaluators on `diff`.

**Questions:** what is the smallest `InnerConfig` that lets a revision
actually move an outcome? Is a plateau detectable from newt-eval scorecards
alone, or does it need the diff?

## Track B — delegated sub-agents

**Reuse:** newt-core's overseer/crew split — a stronger seat authors a
`Plan` DAG, `plan_exec` drives it leaf by leaf through the `CrewRunner`
trait `(op, args, caveats) -> result`, and newt-cli's `LocalCrewRunner` runs
crews in worktrees. The trait is a deliberate injection seam.

**First slice:** a `CrewRunner` implemented in Python and injected through
PyO3 — the one piece of Rust worth writing early. With it, the outer loop
composes inner sub-agents at runtime: a `Swarm` inner that fans a goal out to
several `NewtWorker`s, each with its own gated Rail set, same loop
semantics. This is openJiuwen's "sub-agents reuse the substrate" and it is
the reason shea is in Python.

**Questions:** does the Python runner need the in-process `TurnDriver`
(`submit / poll / cancel`, not yet PyO3-bound) or is ACP enough? Ambient
authority here, so the caveat attenuation newt does per leaf is recorded, not
enforced — is that the right reading for OpenShell-hosted runs?

## Track C — goals, evaluations, verifications

**Reuse:** `shea._native.eval` — `TestCase`, `EvalContext`, `Scorecard`, and
five evaluators (`DiffNonempty`, `DiffApplies`, `RustCompiles`, `TestsPass`,
`PatternMatch`). newt's `adjudicate` pattern: a bounded, tool-less side call
whose verdicts the harness filters, never a second agent turn.

**First slice:** Goal Mode as a Python composition of evaluators plus
user-written predicates, returning `continue | complete | blocked`. A user
writes intentions and verifications as functions over the trial history;
the roadmap owes no other DSL.

## Track D — newtui

**Reuse:** newtui's `Component` / `Flow` / `View` and the exhaustive
`Explorer` with stock properties; `ui.smoke` already runs it in-process.
newt-cli's `parse_with_help` + `dispatch` are library entry points.

**Slices, in order:**

- Python-defined components: a PyO3 bridge so newtui's `Explorer` walks a
  component whose `handle` and `view` are Python. Every shea panel gets the
  acceptance harness for free.
- newt's TUI in-process: `shea._native.run(argv)` calling newt-cli's
  `dispatch` instead of exec'ing the binary. Waits for a reason; newt-cli's
  default features pull the embedded candle summarizer.
- Trial dashboards as newtui panels: the outer loop's rows as live widgets
  (newtui's "Grafana you can drive from a terminal" direction).

## Track E — data science, reporting, open-source EDA

**Reuse:** `shea._native.data` (newt-data: CSV → SQLite, SQL query,
pandas-style summarize) and newt-mcp-data's MCP surface.

**First slice:** an inner loop whose tools are EDA tools, not coder tools —
ingest, query, summarize, plot — with a Goal Mode written for analysis
questions ("is the effect real", "is the report reproducible"). Reports as
plain-text artifacts the user owns.

## Track F — fleets

Inner and outer agents that interact: many outers, each revising its own
inners, sharing an experience store. Depends on A–C. Reuse newt-mesh /
agent-mesh for presence and inference sharing when it matters; not before.

## Upstream — newt-agent branding gaps shea uncovered

Found while rebranding through the runtime seam (newt 0.8.0, 2026-09-04/05).
Candidate issues for newt-agent; each is small.

1. **`.newt` does not follow the brand.** `NEWT_CONFIG_DIR` overrides the
   home config dir in `config.rs`, but `agent_identity.rs` joins `~/.newt`
   directly and ignores it; the project-local `.newt/` walk-up and
   `/etc/newt/` are hardcoded; user-facing hints print `~/.newt/...`
   verbatim. A rebrand should be able to say `.shea`, `~/.shea`, `/etc/shea`
   in one place — a brand-derived config-dir name with `NEWT_CONFIG_DIR`
   honored everywhere, and messages rendered from it.
2. **A rebranded harness commits as newt's account.** `NEWT_BRAND_NAME`
   changes the trailer qualifier (`(shea v0.8.0 …)`) but the author
   name/email fall through to `DEFAULT_AGENT_NAME` / `DEFAULT_AGENT_EMAIL`,
   the newt-agent GitHub user. newt's own rule says a harness never signs
   another's account and never invents an email. So a brand override with
   no identity file should fail closed ("no commit identity configured for
   brand `shea`") or take a `NEWT_BRAND_EMAIL`, not borrow newt-agent's.
   Something unique to the new harness, by construction.
3. **No custom logo means newt's logo.** `brand_logo` falls back to the
   compiled-in newt art when `NEWT_BRAND_LOGO_DIR` is unset or a stem is
   missing, and `brand_active()` keys on the logo dir alone — so a brand
   with a name and no art shows the wrong mascot. Keep custom art (`<prefix>-
   <stem>.txt` per size stem), and when there is none render a **WordArt
   wordmark** from `NEWT_BRAND_NAME` at each stem (10/20/40/80/126/166
   columns), so a rebrand without a designer still looks like itself.

## Findings — cryptographic structures everywhere

The experiment's second output. Two lists, appended as they happen.

**Where they solved a problem:**

- 2026-09-05 — cross-language identity, proven not assumed. A genesis node
  minted by Rust's `MerkleNode` has the same id as the Python dict
  `{"payload": …, "parents": []}` minted by the binding's `content_id`
  (`tests/test_merkle_log.py`). One canonical form, two languages, no
  bespoke encoding — the failure mode the workspace rule warns about is
  tested against rather than hoped away.
- 2026-09-05 — tamper evidence for free. `MerkleLog.node` re-derives the id
  from the stored bytes; flipping one byte of an earlier entry fails the
  walk. No checksum field, no signature scheme, nothing to design.
- 2026-09-05 — "the outer loop edits data, not code" is enforced, not
  advised. A harness config with a callable in it dies at
  `to_canonical_dagcbor` on the way into the log (`tests/test_loop.py`).
  Design rule 2 came free with rule 5.
- 2026-09-05 — an append-only log turns `raise` into data loss, and that
  changes how the code is written. Five of the review's findings were the
  same defect: an exception escaping `NewtWorker.run` (an over-long reply
  line, an unset backend env var, a missing binary, a git failure) aborts
  the outer loop with **no row for the round that failed**. Without a log
  demanding a row per round, each would have looked like ordinary error
  propagation. Every failure is now a trial with `error` set.

**Where they caused one:**

- 2026-09-05 — the crate is Rust. shea's structures are born in Python, so
  every one crosses PyO3 to get an id. A `content-addressable-py` companion
  exists (PyPI 0.1.2, matching `main`) and `merkle` /
  `store` are still `unstable-*` features. Resolved as *both*: the binding
  installs from the crate's `main` via pip for values and ids; `shea._native`
  takes the core crate (git `main`, `unstable-merkle`) for nodes.
- 2026-09-05 — Python cannot build a Merkle node. The binding refuses a
  `ContentId` inside a value (`TypeError: unsupported type ContentId`), so
  parent links cannot be expressed from Python; and `MerkleNode` is not bound
  at all. shea mints nodes in Rust (`src/cas.rs`) and Python only stores,
  verifies, decodes. Upstream candidate for content-addressable-py: encode
  `ContentId` as an IPLD link, expose `MerkleNode`.
- 2026-09-05 — two ratchets, unequal. Cargo locks the git rev of the crate;
  pip has no lock for the `git+…@main` binding, so the Python side moves on
  every install. Tolerable while the binding is tiny; a `uv.lock` is the
  obvious fix when it stops being.
- 2026-09-05 — a hash-chained log makes trial content a hygiene problem
  with no undo. An endpoint that reaches a trial is in the chain forever,
  so scrubbing has to be by value over the whole row (newt puts the
  endpoint in JSON-RPC error text and in retry warnings, not only in
  `metrics.endpoint`). A mutable store would have allowed a later redaction.
- 2026-09-05 — pyo3 version skew across the line. The binding pins pyo3
  0.29, newt pins 0.28; one extension module can link only one, so the
  binding could not be registered inside `shea._native` even if wanted.
  Separate modules sidestep it; a line-wide pyo3 pin would remove it.

## Upstream — newt-agent worker findings (verified live 2026-09-05)

Found while building `NewtWorker`; each is a candidate newt-agent issue.

1. **`NEWT_DEFAULT_MODEL` and `set_session_model` are no-ops.** newt-core
   injects a loopback-Ollama fallback backend whenever no `[[backends]]`
   exist, so `select_backend` never reaches the discovery branch that reads
   `NEWT_DEFAULT_MODEL`; and the worker stores `set_session_model`'s
   override without ever reading it. Only `--backend-*` flags pin a model.
   Side effect: newt-eval's `--model` / `just eval-live MODEL` silently
   evaluates the fallback model.
2. **One bad drop-in refuses every config-resolving command.** A
   `~/.newt/backends/*.toml` carrying an old probe marker plus a model makes
   `newt config` and `newt worker` exit 1 ("Refusing to guess");
   `--backend-endpoint` does not bypass it, only `--config-dir` does. A
   downstream host cannot inherit the operator's `~/.newt` until the
   operator repairs it by hand.
3. **The worker's ACP is bespoke.** Method names (`initialize`,
   `new_session`, `set_session_model`, `prompt`) and param names differ from
   agentclientprotocol.com's (`session/new`, `session/prompt`, …); a
   spec-conformant client gets `-32603 method not found`. Cargo.toml already
   carries the TODO to adopt the `agent-client-protocol` crate.
4. **`NEWT_CODER` is read two incompatible ways, and the documented form
   breaks startup.** `newt-cli/src/lib.rs:653` declares `--coder` with
   `env = "NEWT_CODER"`, so clap parses the variable as a bool value and
   rejects anything but `true`/`false`; `newt-acp-worker/src/server.rs:310`
   reads the same variable as `== "1"`. The docs at `newt-cli/src/lib.rs:1788`
   say `NEWT_CODER=1` in a unit file works. Verified: `NEWT_CODER=1 newt
   worker` exits 2 with `invalid value '1' for '--coder'`, while
   `NEWT_CODER=true` starts but leaves the server-side opt-in off. The
   process-wide coder switch is broken in both directions.
5. **`diff_applied` can be true while `empty_diff` is true** on the coder
   path (untracked new files count as written but the unstaged diff is
   empty). Callers must score on their own diff, which shea now does.

## References

- openJiuwen: Beyond Static Harnesses for Long-Horizon Coding Agents —
  https://arxiv.org/html/2608.27969 · code: https://github.com/openJiuwen-ai/jiuwenswarm
- Christina Lee, "Meta harness makes 10 times better Kimi K3 chip" —
  https://www.luoluo.ai/blog/kimi-k3
- newt-agent `docs/decisions/agent_line_architecture.md`; newt-core
  `agentic/{driver,crew_tool,plan_exec,adjudicate}.rs`; newt-acp-worker;
  newt-eval; newtui README.
