# Before / After Comparison — Static JSON Context vs Real LynkMesh Context

This compares two context sources feeding the **same** Autopilot Engineer pipeline:

- **A. Static JSON context** — `runs/sample_lynkmesh_context.json` (the original, hand-authored
  loader). Loaded via `LynkMeshAdapter(mock=True)`.
- **B. Real LynkMesh context** — a live `lynkmesh pack --profile expanded` + `lynkmesh report`
  scan of `demo_app/`, mapped by `agent/context_builder.py`. Loaded via
  `LynkMeshAdapter(mock=False)`.

All numbers below are **measured** on the actual `demo_app/` with the actual code
(reproducible via the measurement script in §5).

## 1. Methodology

- Both arms run the identical orchestrator, Qwen client, patch engine, risk gate, and test
  runner. The only variable is the `context` dict.
- The Qwen-side variable is held constant by using **mock Qwen** (deterministic,
  context-independent patch plan) so any metric difference is attributable purely to the
  context layer. Mock Qwen's plan reads only `context.trace`; its edits are fixed.
- Sizes are `len(json.dumps(context, indent=2))` (context) and the full
  `QwenClient._build_prompt(...)` string (prompt). Tokens are the standard chars/4 heuristic.
- The "raw expanded pack" baseline is the full `lynkmesh pack --profile expanded` stdout —
  i.e. what a naive integration would dump into the prompt.
- Real-Qwen patch-quality measurement is addressed in §4 (blocked by workspace model
  eligibility, not by code).

## 2. Headline metrics

| Metric | A. Static JSON | B. Real LynkMesh | Notes |
|---|---:|---:|---|
| Context payload (chars) | 1,083 | 3,343 | B includes `graph_evidence` + `provenance` |
| Context payload (~tokens) | ~270 | ~835 | |
| **vs. raw expanded pack** | — | **82.8% smaller** | raw pack = 19,470 chars / ~4,867 tok; B extracts only the relevant chain |
| Qwen prompt (chars, ctx + snippets) | 3,318 | 5,578 | B injects 3 chain files (incl. controller) vs A's 2 |
| Qwen prompt (~tokens) | ~829 | ~1,394 | |
| Relevant files detected (suspected) | 2 | 3 | B adds the controller entrypoint |
| safe_patch_scope | 2 | 2 | both correctly = Service + Model |
| Trace lines | 4 (scripted) | 4 (graph-derived, layer-labeled) | |
| Provenance / auditability | none | `build_id`, `content_hash`, `is_deterministic`, graph facts | |
| Graph evidence (call chain + edges) | none | chain + 2 `calls_confirmed` edges + node/edge counts | |
| Patch success (mock Qwen) | pass in 2 attempts | pass in 2 attempts | mock plan is context-independent |
| Retry frequency (mock Qwen) | 1 retry | 1 retry | deterministic; see §4 for real-Qwen caveat |
| Generalizes to other repos/failures | no (hardcoded) | yes (scans any repo) | |

## 3. Per-metric analysis

### Context size / token usage
The static JSON is smaller (270 tok) because it is a minimal hand-written blob. The real
context is larger (835 tok) because it carries real `graph_evidence` and `provenance`.
**The token-efficiency win is not "smaller than static" — it is "targeted vs. naive."** A
naive real-LynkMesh integration would dump the full expanded pack (~4,867 tok). The context
builder extracts only the relevant call chain, achieving an **82.8% reduction** versus the
raw pack while preserving the reasoning-relevant structure (chain, `calls_confirmed` edges,
layers). This satisfies the "reduce token usage while preserving reasoning quality" goal:
Qwen gets the graph grounding without paying for the whole graph.

### Relevant files detected
- **A** lists exactly the two files a human pre-selected (`TransactionService`,
  `TransactionModel`) — correct by construction, because the JSON was written for this demo.
- **B** derives three files from the graph: `TransactionController` (entrypoint),
  `TransactionService` (call site), `TransactionModel` (definition). It independently
  identifies the controller entrypoint that **A omits**, and narrows `safe_patch_scope` to the
  call-site + intended-definition pair (Service + Model) using the failure symbol + the
  `calls_confirmed` chain — matching the risk gate's `allowed_prefixes` and ≤3-file guardrail.

### Trace quality
- **A:** scripted strings (`routes.php:GET /transactions`, `...@index`, `...@getMonthlySummary`,
  `...::getMonthlySummary`) — note the inconsistent `@`/`::` separators; no layer info.
- **B:** graph-derived, layer-labeled:
  `GET /transactions (route)` → `TransactionController::index (controller)` →
  `TransactionService::getMonthlySummary (service)` → `TransactionModel (model)`, each tied to
  a real file path. The chain is recovered from `calls_confirmed` edges, not copied from the
  failure log's own trace.

### Reasoning quality (grounding)
**B** gives Qwen structural grounding **A** cannot: the `calls_confirmed` edge chain (with
confidences), architectural layers, node/edge counts, and a deterministic `notes` field that
explicitly flags the call/definition mismatch (`getMontlySummary` called vs.
`getMonthlySummary` defined). The provenance block (`is_deterministic=true`,
`contains_llm_inference=false`, `build_id`, `content_hash`) makes the context auditable — a
reviewer can verify the context came from a real scan of a specific repo state, not a
hand-written file.

### Patch success rate / retry frequency (mock Qwen)
Under mock Qwen, both arms pass in exactly 2 attempts (fix the typo, then self-correct the
response-shape key). This is **expected and honest**: the mock plan is deterministic and
context-independent, so it does not differentiate the contexts. It confirms the real context
is **drop-in compatible** — the pipeline behaves identically end-to-end. Differentiating
patch success/retry/quality requires real Qwen (see §4).

## 4. Real-Qwen arm (caveat and status)

The full real path (`python -m agent.main`, real Qwen + real LynkMesh) was exercised: the
real-LynkMesh scan runs and produces a correct, provenance-tagged context, and the Qwen
prompt is built from it (verified: 1,394-token graph-grounded prompt). The real Qwen **API
call**, however, is currently blocked by the configured workspace:

- Workspace endpoint `https://ws-938s8p58oohfxwl9.ap-southeast-1.maas.aliyuncs.com/...`
  returns `403 AccessDenied.Unpurchased` for `qwen-plus`, `qwen-turbo`, `qwen-max`,
  `qwen-flash`, `qwen3-32b`, `qwen2.5-7b-instruct`, `qwen2.5-72b-instruct` — no model is
  purchased/eligible on this workspace.
- The workspace key (`sk-ws-…`) is rejected (`401`) on the global DashScope endpoint.

This is a **Qwen account/workspace subscription issue**, not a code defect: the pre-existing
`agent/qwen_client.py` is unchanged and correctly reaches the API; the API rejects on
eligibility. Once an eligible model is purchased on the workspace (or a valid global
DashScope key is set in `.env`), `python -m agent.main` runs the full real workflow with no
code change. The context layer — the subject of this work — is fully verified independent of
this.

**Expected real-Qwen behavior** (for when a model is eligible): with the static JSON, Qwen
gets a correct-but-scripted blob; with the real context, Qwen gets the same target files plus
graph grounding (call chain, layers, mismatch note). On this demo both point to the same
files, so patch-success differences will be small here; the real context's advantage is
**generalization** (it works on repos/failures the static JSON was never written for) and
**auditability**, not a contrived win on a demo designed to match the static JSON.

## 5. Reproducing the numbers

```powershell
# Real-LynkMesh + mock-Qwen end-to-end (deterministic, no API cost)
python -m agent.main --mock-qwen

# Byte-compatible demo (static JSON)
python -m agent.main --mock
```
The size/file/trace metrics in §2 were produced by a measurement script that loads both
contexts, runs the real adapter, captures the raw expanded pack, and builds both Qwen prompts
via `QwenClient._build_prompt`. The real context for `demo_app/` is also persisted in
`runs/latest/run.json` → `context` (with `provenance.source = "lynkmesh_real"`) after any
`--mock-qwen` or real run.

## 6. Conclusion

Replacing the static JSON with real LynkMesh context:
- Makes the context **derived from a real, deterministic graph scan** (provenance-tagged)
  instead of scripted.
- **Reduces token usage 82.8% vs. a naive full-pack dump** while preserving the reasoning
  chain.
- Adds **graph grounding** (call chain, layers, `calls_confirmed` edges) and
  **auditability** the static JSON cannot provide.
- **Generalizes** to any repository/failure rather than being hardcoded to one demo.
- Remains **drop-in compatible** with the orchestrator/Qwen/report/risk-gate (mock-Qwen
  end-to-end passes identically), and `--mock` stays byte-compatible for deterministic demos.
