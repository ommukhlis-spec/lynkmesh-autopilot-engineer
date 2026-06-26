# LynkMesh Open — Capabilities Reference

Source repository: `lynkmesh-open` (local sibling repo; installed editable as `lynkmesh`
v0.1.0a0). LynkMesh Open is an "open-core deterministic code graph foundation for legacy
codebases" (Apache-2.0, research preview). This document records the capabilities relevant
to integrating it as the real context provider for the Autopilot Engineer.

All findings below were verified by reading `lynkmesh/cli/main.py`, `pyproject.toml`, the
contract modules, and by running the CLI against `demo_app/`.

## 1. CLI entrypoints

Console script (`pyproject.toml` `[project.scripts]`):
```
lynkmesh = "lynkmesh.cli.main:main"
```

Subcommands (from `lynkmesh/cli/main.py` `build_parser()`):

| Command | Purpose | Builds graph? |
|---|---|---|
| `lynkmesh doctor [--json] [--quiet]` | Local environment diagnostics | No |
| `lynkmesh report <path> [--pretty] [--quiet]` | MeshContext Report (JSON to stdout) | Yes |
| `lynkmesh pack <path> [--profile compact\|balanced\|expanded] [--pretty] [--quiet]` | AI Context Pack (JSON to stdout) | Yes |
| `lynkmesh benchmark <path> [--profile ...] [--profiles a,b,c] [--pretty] [--quiet]` | Token benchmark (JSON to stdout) | Yes |

Conventions:
- **JSON goes to stdout**; human diagnostics go to stderr. `--quiet` suppresses the
  `diag()` progress lines (but pipeline warnings and final error lines still go to stderr).
- `--pretty` indents + `sort_keys=True`; without it, output is compact `sort_keys=True`.
- The path is a required positional directory argument. There is **no** `--format` or
  `--output` flag — stdout is always JSON.
- No files are written, no network access, no LLM inference (guarantees enforced in code).

Verified run on `demo_app/`:
```
lynkmesh doctor --quiet          -> "lynkmesh doctor: ready (v0.1.0a0)"
lynkmesh report <demo_app> --quiet            -> 0, JSON on stdout
lynkmesh pack <demo_app> --profile expanded --quiet  -> 0, JSON on stdout
```

## 2. Graph generation

`report` and `pack` both build the graph via `_run_pipeline(project_path)` ->
`IncrementalPipeline(cache_dir=None).run(path, skip_cache_save=True)` (no cache, no writes).
The pipeline runs the PHP bridge, serializes the graph, and projects it into a MeshContext
Report / AI Pack.

**Language support:** detected by extension (`.php`, `.py`, `.js/.jsx`, `.ts/.tsx`, `.java`,
`.go`, `.cs`, `.rb`, `.rs`). PHP is the first-class path: a bundled
`lynkmesh/ingestion/php_bridge/parser.php` is invoked via `php parser.php <file> --minify`,
executed in parallel (ThreadPool on Windows, ProcessPool on Unix). The bridge returns
classes, methods, functions, imports, and calls.

**Graph representation (serialized payload):** `schema_version`, `version`, `stats`
(`nodes, edges, files, classes, methods, functions, external`), `nodes[]`, `edges[]`. Each
node carries `identity.{layer, name, qualified_name, file_path, extra{class, entry,
entry_type, params, return_type, visibility}}`. Each edge carries
`identity.{semantic, confidence_str, source_identity, target_identity, metadata{line}}`.
Observed `identity.layer` values: `controller`, `service`, `model`. Observed edge
`semantic` values: `request_flow`, `data_access`, `structural_contains`.

**Route→controller→service→model chain:** not modeled as a first-class query, but fully
recoverable from the graph. The expanded AI Pack exposes `calls_confirmed` edges that spell
out the chain, and `architecture_context` candidate lists identify entrypoint/service/data
layers (see §4). Conventional entrypoint detection (`public/index.php`, `routes/web.php`)
is heuristic; the demo app uses a custom `routes.php`, which is detected as a node but not
classified as a framework route.

## 3. MeshContext generation

"MeshContext" is the umbrella for two public artifacts produced by
`lynkmesh/semantic/contracts/`:

- **MeshContext Report** (`build_mesh_context_report`) — deterministic, conservative,
  privacy-safe aggregate facts. Does **not** take a failure signature; it describes the whole
  project.
- **MeshContext AI Context Pack** (`build_mesh_context_ai_pack`) — a compact/balanced/expanded
  projection of the report for AI consumption, with an `evidence_index` of citable
  nodes/edges.

Neither artifact is failure-targeted. Targeting (mapping a CI failure onto the graph) is the
job of our `agent/context_builder.py`.

## 4. JSON outputs (verified shapes)

### `lynkmesh report <path>` → MeshContext Report
Top-level fields: `schema_version`, `report_type:"mesh_context_report"`, `generated_at`,
`project{display_name,primary_language,languages}`, `build{build_id,graph_id,content_hash,
pipeline_schema_version,serializer_schema_version,...}`, `graph_facts{node_count,edge_count,
node_type_breakdown,edge_type_breakdown,confidence_distribution}`, `entrypoints[]`,
`languages{primary,supported,mix}`, `hotspots[]`, `risk_candidates[]`, `dependency_summary
{layers,layer_edges,cycles_detected,cross_layer_candidates}`, `limitations[]`,
`llm_instructions{role,allowed_inferences,forbidden,confidence_policy,token_policy}`,
`provenance{generator,generator_version,is_deterministic,contains_llm_inference,sections}`.

### `lynkmesh pack <path> --profile expanded` → AI Context Pack (the one we use)
Top-level fields: `schema_version:"mesh_context_ai_pack.v0.1"`, `profile`, `purpose:
"ai_consumption"`, `project_identity{build_id,content_hash,display_name,graph_id}`,
`executive_context{node_count,edge_count,node_type_breakdown,edge_type_breakdown,...}`,
`architecture_context{entrypoint_candidates,service_candidates,data_access_candidates,
dominant_components,cross_cutting_candidates}`, `dependency_context`, `hotspot_context`,
`risk_context`, `evidence_index{nodes,edges,sections,profile}`, `context_budget
{estimated_input_tokens,estimated_token_reduction_percent,...}`, `guardrails
{deterministic_facts_only,contains_llm_inference,...}`, `omissions`, `ai_task_guide`.

**`evidence_index` is the key integration surface** (only populated by `expanded`):

- `nodes`: `{ "node:method:TransactionController::index": { id, kind:"node", label,
  path:"app/Controllers/TransactionController.php", qualified_name, type:"method",
  confidence } }`. `path` is **relative to the scanned repo** (privacy-safe; no absolute
  paths). File nodes have no `qualified_name`; class/method/function nodes do. One node may
  appear as `__unsafe_redacted__` when the privacy scanner strips it.
- `edges`: `{ "edge:<src>-><tgt>:<type>": { id, kind:"edge", source, source_label, target,
  target_label, type, confidence } }`. Edge `type` ∈ {`calls_confirmed`, `contains`,
  `defined_in`, ...}. `calls_confirmed` edges carry a numeric `confidence` (e.g. "0.9").

For `demo_app/`, the expanded pack's `calls_confirmed` edges are exactly:
```
TransactionController::index           -> TransactionService::getMonthlySummary  (0.9)
TransactionService::getMonthlySummary  -> TransactionModel::getMonthlySummary     (0.9)
```
This is the route→controller→service→model chain, recoverable deterministically.

> `compact` pack omits `full_raw_node_listing` / `full_raw_edge_listing` —
> `evidence_index.nodes`/`.edges` are empty. **`expanded` is required** for our use.

### `lynkmesh benchmark <path>` → token estimates per profile
Reports `estimated_input_tokens` and `estimated_token_reduction_percent` per profile, plus a
`serialized_graph_payload` baseline. Useful for the before/after comparison doc.

## 5. MCP capabilities

**No MCP server is implemented.** MCP is mentioned only as a planned/intended consumer
(`mesh_context_ai_pack.py` docstring: "intended for direct AI/MCP-client consumption";
`incremental_pipeline.py`: "for downstream CLI/MCP consumers"). The README lists planned MCP
tools (`ping`, `get_status`, `scan_project`, `build_graph`, `analyze_impact`,
`trace_dependencies`, ...) but none exist in code. **Integration is therefore CLI/library,
not MCP.**

## 6. Python import API (library mode)

Available, with deferred imports so `doctor`/`--help` stay cheap:
```python
from lynkmesh.pipeline.incremental_pipeline import IncrementalPipeline
from lynkmesh.semantic.contracts import (
    build_mesh_context_report, build_mesh_context_ai_pack,
    find_unsafe_report_strings, find_unsafe_ai_pack_strings,
)
from lynkmesh.core.graph_serializer import serialize_graph

pipeline = IncrementalPipeline(cache_dir=None)
run = pipeline.run(project_path, skip_cache_save=True)
payload = run.serialized_payload            # full nodes/edges graph
report = build_mesh_context_report(payload, project_display_name=...,
                                   primary_language=..., languages=...,
                                   pipeline_schema_version=..., generator_version=...)
pack   = build_mesh_context_ai_pack(report.to_dict(), profile="expanded", graph_source=payload)
```
`serialized_payload` is richer than the public pack (absolute `file_path`s, `identity.layer`,
edge `semantic`) but is an internal shape and not privacy-sanitized. Our adapter uses the
**CLI** (privacy-safe, isolated, deterministic) rather than the internal payload; the
context builder consumes the public expanded pack's `evidence_index`.

## 7. Runtime requirements

- **Python ≥ 3.11** (`MIN_PYTHON = (3, 11)`). Verified on 3.13.
- **No runtime dependencies** (`dependencies = []`); dev: `pytest>=8`.
- **PHP CLI on PATH** — required for the PHP bridge (`shutil.which("php")`). Verified PHP 8.5.
- **Determinism guard:** the pipeline raises `OSError` unless `PYTHONHASHSEED=0`
  (`verify_pipeline_determinism()`). The adapter sets this in the LynkMesh subprocess env.
- `lynkmesh doctor --json` reports `php_bridge.available`, `python_version_supported`, and
  `deterministic_mode_active` for environment self-checks.

## 8. Smoke repository

`lynkmesh-open-smoke` (and `lynkmesh-open/evals/before_after/runs/mini_auth_shop_php_001/`)
contain real example artifacts (`report_output.json`, `pack_output.json`,
`benchmark_output.json`) for a `mini_auth_shop_php` project (61 nodes, 99 edges). These were
used to confirm the output schemas before integration.

## 9. Integration decision (summary)

- Invoke `lynkmesh pack <repo> --profile expanded --quiet` (evidence_index) **and**
  `lynkmesh report <repo> --quiet` (provenance) as isolated subprocesses with
  `PYTHONHASHSEED=0` and a timeout.
- Parse stdout JSON; treat stderr as diagnostics.
- Map the failure onto the graph in `agent/context_builder.py` (no MCP, no internal
  payload) to emit the existing context schema plus a `provenance` block.
- Fall back to the static JSON (tagged) if `lynkmesh`/`php` is unavailable or the scan fails.
