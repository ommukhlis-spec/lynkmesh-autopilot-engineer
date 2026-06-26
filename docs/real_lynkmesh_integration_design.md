# Real LynkMesh Integration — Design

Goal: replace the static JSON context layer with a real LynkMesh Open graph scan, while
keeping `--mock` byte-compatible and leaving the orchestrator, patch engine, risk gate, and
dashboard flow untouched. Only the context layer changes.

## 1. Architecture (before → after)

```
BEFORE                                   AFTER
CI Failure                               Repository path (configurable)
   ↓                                         ↓
sample_lynkmesh_context.json             LynkMesh scan (pack --profile expanded + report)
   ↓                                         ↓  (PYTHONHASHSEED=0, timeout, subprocess)
Qwen                                     ContextBuilder: failure → graph → targeted context
   ↓                                         ↓
Patch                                    Qwen  (same prompt, now graph-grounded context)
   ↓                                         ↓
Test                                     Patch → Test → Self-Correction → Report  (unchanged)
```

The orchestrator still calls `self.lynkmesh.get_context_for_failure(failure_log)` once and
passes the result to Qwen. The contract is identical; only the adapter's internals change.

## 2. Components

### `agent/lynkmesh_adapter.py` (rewritten)
`LynkMeshAdapter(repo_path, *, mock, context_path, root_dir, allowed_prefixes, timeout,
profile, fallback_to_static, lynkmesh_bin)`.

`get_context_for_failure(failure_log) -> dict`:
- **mock=True** → `json.loads(context_path)` returned **untouched** (byte-compatible demo;
  no injected fields). The orchestrator prints `[LYNKMESH CONTEXT] loaded`.
- **mock=False** → run LynkMesh, build context, tag `provenance.source="lynkmesh_real"`,
  print `[LYNKMESH SCAN] ok source=lynkmesh_real nodes=… edges=… calls=… build_id=…`.

`_run_lynkmesh(args, required)`:
- Resolves the binary via `shutil.which("lynkmesh")` (overridable); pre-checks `php` on PATH.
- `subprocess.run([bin, *args], capture_output=True, text=True, timeout=timeout,
  env={**os.environ, "PYTHONHASHSEED": "0"})`. Runs `pack <repo> --profile expanded --quiet`
  (required) and `report <repo> --quiet` (best-effort; a report failure is logged, not fatal).
- Parses stdout JSON. Non-zero exit / empty stdout / JSON error → `RuntimeError`.
- `TimeoutExpired` → `RuntimeError("… timed out after {timeout}s")`.

### `agent/context_builder.py` (new)
`ContextBuilder.build(report, pack, failure_log, repo_path, root_dir, allowed_prefixes)`.
Pure function over the parsed JSON; no I/O, no LLM. Algorithm:

1. **Parse failure_log** → `{message, type, symbol, called_class, called_method, route}`
   (regex on `FAIL:` line, HTTP method+path, `Class::method`/`->method`).
2. **Parse graph** from `pack.evidence_index.nodes` (id→node) and `.edges`. Build
   `calls_confirmed` adjacency `source_id → [(target_id, conf)]`.
3. **Rebase paths** to project-root-relative: `prefix = repo_path.relative_to(root_dir)`
   → `<prefix>/<lynkmesh_path>` (e.g. `demo_app/app/Services/…`). Skip `__unsafe_redacted__`.
   No hardcoded paths — prefix is computed from the configured repo path.
4. **Derive the chain** route→controller→service→model: start from the
   `architecture_context.entrypoint_candidates` method node that has an outgoing
   `calls_confirmed` edge (prefer non-constructor); follow `calls_confirmed` edges
   downstream. (The graph reveals the *intended* chain even though the called method
   `getMontlySummary` is a typo and absent from the graph.)
5. **Emit the existing schema** plus extras:
   - `failure{type,message,symbol,route}`, `trace[]` (route + `file :: qualified_name
     (layer)` per chain node), `suspected_files[]` (all chain files), `impact[]` (route +
     entrypoint + feature labels), `safe_patch_scope[]` (call-site + intended-definition
     files, filtered to `allowed_prefixes`), `confidence` (min `calls_confirmed` conf),
     `notes` (deterministic summary of chain + call/definition mismatch).
   - `graph_evidence{chain, calls_confirmed, node_count, edge_count}` — compact, only the
     relevant chain (token reduction vs. dumping the whole graph).
   - `provenance{source, build_id, content_hash, graph_id, generator, generator_version,
     is_deterministic, profile, scan_path, graph_facts, calls_confirmed_count}`.

### `agent/config.py`, `agent/orchestrator.py`, `agent/main.py`
- `AgentConfig` gains `lynkmesh_repo_path` (default `demo_app`), `lynkmesh_timeout`,
  `lynkmesh_profile`, `lynkmesh_fallback_to_static`. `context_json` retained for mock/fallback.
- Orchestrator gains `mock_context: bool | None = None` (defaults to `mock_qwen`); constructs
  `LynkMeshAdapter(...)` with the new params. **Flow unchanged.**
- `main.py` flags: `--mock` (combined deterministic, exactly as today), `--mock-qwen`,
  `--mock-context` (default to `--mock`), `--repo`, `--lynkmesh-timeout`, `--no-fallback`.

## 3. Failure handling & fallback

```
get_context_for_failure (mock=False)
  ├─ try: _run_lynkmesh(pack) + _run_lynkmesh(report) + ContextBuilder.build(...)
  │    └─ success → context (source=lynkmesh_real)
  └─ except Exception:
       ├─ fallback_to_static=False → raise RuntimeError
       └─ fallback_to_static=True and static JSON exists
            → static JSON + provenance{source=static_fallback, fallback_reason}
```
Failure cases handled: `lynkmesh` not on PATH, `php` not on PATH, repo path missing,
`TimeoutExpired`, non-zero exit, empty stdout, JSON decode error, context-builder error.
The fallback is **tagged** (`source=static_fallback` + `fallback_reason`) so it is never
silent — reports/run.json always show which source produced the context. The real path never
*requires* the static JSON; fallback is a safety net for demo robustness.

## 4. Expected context schema (real mode)

```json
{
  "failure": { "type": "undefined_method", "message": "Call to undefined method TransactionModel::getMontlySummary()",
               "symbol": "TransactionModel::getMontlySummary", "route": "GET /transactions" },
  "trace": [
    "GET /transactions (route)",
    "demo_app/app/Controllers/TransactionController.php :: TransactionController::index (controller)",
    "demo_app/app/Services/TransactionService.php :: TransactionService::getMonthlySummary (service)",
    "demo_app/app/Models/TransactionModel.php :: TransactionModel (model)"
  ],
  "suspected_files": [ "demo_app/app/Controllers/TransactionController.php",
                       "demo_app/app/Services/TransactionService.php",
                       "demo_app/app/Models/TransactionModel.php" ],
  "impact": [ "GET /transactions", "TransactionController::index HTTP entrypoint",
              "get monthly summary (service)", "transaction model (model)",
              "TransactionModel::getMontlySummary response contract" ],
  "safe_patch_scope": [ "demo_app/app/Services/TransactionService.php",
                        "demo_app/app/Models/TransactionModel.php" ],
  "confidence": 0.8,
  "notes": "LynkMesh graph traced … via calls_confirmed edges (confidence=0.8). … call/definition mismatch. …",
  "graph_evidence": { "chain": [...], "calls_confirmed": [...], "node_count": 14, "edge_count": 16 },
  "provenance": { "source": "lynkmesh_real", "build_id": "...", "content_hash": "...",
                  "is_deterministic": true, "profile": "expanded", "graph_facts": {...},
                  "calls_confirmed_count": 2, ... }
}
```
All existing fields are present in the same shape. New fields (`graph_evidence`,
`provenance`, extra `failure` sub-fields) are additive and ignored by consumers that do not
read them.

## 5. Compatibility with the existing orchestrator

- `get_context_for_failure(failure_log) -> dict` signature preserved.
- `qwen_client._build_prompt` reads `safe_patch_scope`/`suspected_files` (present,
  root-relative, within `allowed_prefixes`) and dumps the whole context — works unchanged.
- `qwen_client._mock_patch_plan` reads `trace` — present.
- `report_writer._to_markdown` reads `failure.message` and `trace` — present.
- Risk gate `allowed_prefixes` (`demo_app/app/`, `demo_app/tests/`) honored: `safe_patch_scope`
  = `[demo_app/app/Services/…, demo_app/app/Models/…]`, both in scope, ≤3 files (gate limit).
- Patch engine resolves `root_dir / rel_file` — paths are root-relative. ✓
- `--mock` output is byte-identical to the starter (verified).

## 6. Determinism & privacy

- **Determinism:** LynkMesh runs with `PYTHONHASHSEED=0` (its guard requirement); CLI emits
  `sort_keys=True` JSON. `provenance.is_deterministic=true`, `contains_llm_inference=false`.
  Same repo + same LynkMesh version → same context (modulo build_id/content_hash which are
  content-derived hashes).
- **Privacy:** LynkMesh strips absolute paths; `evidence_index` paths are repo-relative. The
  adapter rebases them to project-root-relative for the patch engine. The one
  `__unsafe_redacted__` node is skipped. `scan_path` in provenance is the configured repo
  path (local only; the report writer already redacts local paths in test output).

## 7. Sequence (real mode)

```
orchestrator.run()
  → reset_demo_app; test_before (fail)
  → lynkmesh.get_context_for_failure(failure_log)
       subprocess: lynkmesh pack <repo> --profile expanded --quiet   (env PYTHONHASHSEED=0)
       subprocess: lynkmesh report <repo> --quiet                    (best-effort)
       ContextBuilder.build(report, pack, failure_log, …)
       ← context {source=lynkmesh_real, trace, safe_patch_scope, provenance, …}
  → for attempt in 0..max_retries:
       qwen.generate_patch_plan(failure_log, context, retry_feedback)
       patch_engine.apply_patch_plan  (risk_gate validates)
       test_runner.run
       if passed: break else retry_feedback = test output
  → report_writer.write(payload)   (context + provenance in run.json/report)
```

## 8. Verification (see plan §Verification)

- `python -m agent.main --mock` → byte-identical demo (static JSON). ✓ verified.
- `python -m agent.main --mock-qwen` → real LynkMesh + mock Qwen, `source=lynkmesh_real`,
  tests pass after self-correction. ✓ verified.
- `python -m agent.main` → real Qwen + real LynkMesh. Real-LynkMesh path verified; real-Qwen
  arm requires an eligible model on the configured workspace (see comparison doc).
- Fallback: `--no-fallback` raises on LynkMesh failure; default falls back to tagged static.
