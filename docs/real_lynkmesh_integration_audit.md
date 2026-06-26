# Real LynkMesh Integration — Audit of the Current Adapter

Status: pre-integration audit of `agent/lynkmesh_adapter.py` (the starter implementation).
Purpose: document exactly how context is loaded today, what it assumes, and what fields the
rest of the system consumes, so the real-LynkMesh replacement can preserve compatibility.

## 1. The current adapter

`agent/lynkmesh_adapter.py` (original, 21 lines):

```python
class LynkMeshAdapter:
    """Starter adapter.

    In the final version, replace this JSON loader with a call to LynkMesh MCP/API.
    """

    def __init__(self, context_path: Path) -> None:
        self.context_path = context_path

    def get_context_for_failure(self, failure_log: str) -> dict[str, Any]:
        if not self.context_path.exists():
            raise FileNotFoundError(f"LynkMesh context not found: {self.context_path}")
        return json.loads(self.context_path.read_text(encoding="utf-8"))
```

### How it loads context
- The adapter is constructed with a single filesystem path: `config.context_json`, which
  resolves to `runs/sample_lynkmesh_context.json` (`agent/config.py:36`).
- `get_context_for_failure(failure_log)` reads that file, parses it as JSON, and returns the
  dict verbatim.
- **The `failure_log` argument is completely ignored.** The same context is returned for
  every failure, regardless of input. There is no scan, no graph, no analysis — only a
  file read.

### What it assumes
- A hand-authored JSON file exists at a fixed path and contains the full context.
- The file's contents are correct for the current demo scenario (two intentional PHP bugs).
- The repository never changes in a way that invalidates the scripted context.
- No LynkMesh tooling is present or invoked.

These assumptions are what make the workflow "appear scripted": the codebase intelligence is
a static blob, not a derived artifact.

## 2. How the orchestrator uses the adapter

`agent/orchestrator.py`:
```python
self.lynkmesh = LynkMeshAdapter(config.context_json)
...
context = self.lynkmesh.get_context_for_failure(failure_log)
print("[LYNKMESH CONTEXT] loaded")
...
patch_plan = self.qwen.generate_patch_plan(failure_log, context, retry_feedback=retry_feedback)
```
- The adapter is constructed once with the JSON path.
- `get_context_for_failure(failure_log)` is called once per run, before the first Qwen attempt.
- The returned `context` dict is passed straight into `QwenClient.generate_patch_plan` and is
  also embedded in the final `run.json` / remediation report payload under `payload["context"]`.

**Contract the orchestrator relies on:** a callable `get_context_for_failure(failure_log: str)
-> dict`. The real adapter must preserve this signature so the orchestrator flow is unchanged.

## 3. Fields the rest of the system expects from `context`

The context dict is consumed in three places. The real adapter must populate these fields
(in the same shape) for the existing Qwen client and report writer to keep working.

### `agent/qwen_client.py` — `_build_prompt` and `_mock_patch_plan`
- `context.get("safe_patch_scope")` — **primary** source of files whose source is read and
  injected into the Qwen prompt as `SAFE FILE CONTENTS`. Falls back to
  `context.get("suspected_files")` if `safe_patch_scope` is absent.
- The **entire** context dict is serialized (`json.dumps(context, indent=2)`) into the prompt
  under `LYNKMESH DETERMINISTIC CONTEXT JSON`.
- `context.get("trace", [])` — used by the mock patch plan for `uses_context_trace`.
- Paths in `safe_patch_scope`/`suspected_files` must be **relative to the project root**
  (e.g. `demo_app/app/Services/TransactionService.php`), because `_collect_file_snippets`
  resolves them as `self.root_dir / rel` and the risk gate validates them against
  `allowed_prefixes` (`demo_app/app/`, `demo_app/tests/`).

### `agent/report_writer.py` — `_to_markdown`
- `context.get("failure", {}).get("message", "Unknown failure")` — the report's "## Failure"
  heading.
- `context.get("trace", [])` — rendered as the "## LynkMesh Trace" bullet list.

### The static JSON schema (`runs/sample_lynkmesh_context.json`)
```json
{
  "failure": { "type": "undefined_method", "message": "..." },
  "trace": [ "routes.php:GET /transactions", "...@index", "...@getMonthlySummary", "...::getMonthlySummary" ],
  "suspected_files": [ "demo_app/app/Services/TransactionService.php", "demo_app/app/Models/TransactionModel.php" ],
  "impact": [ "GET /transactions", "monthly transaction summary", "transaction report API contract" ],
  "safe_patch_scope": [ "demo_app/app/Services/TransactionService.php", "demo_app/app/Models/TransactionModel.php" ],
  "confidence": 0.92,
  "notes": "..."
}
```

## 4. Gap analysis

| Concern | Current adapter | Required for real integration |
|---|---|---|
| Source of context | Static JSON file | Live LynkMesh graph scan of a repo path |
| `failure_log` used | Ignored | Drives failure symbol + route extraction |
| Repo path | Hardcoded JSON path | Configurable, no hardcoded local paths |
| Determinism | n/a (static) | LynkMesh requires `PYTHONHASHSEED=0` |
| Failure handling | `FileNotFoundError` only | Timeout, missing `lynkmesh`/`php`, non-zero exit, JSON parse errors |
| Fallback | None | Graceful fallback to static JSON (tagged) for demo robustness |
| Provenance | None | `build_id`, `content_hash`, `is_deterministic`, graph facts |
| Schema compatibility | n/a | Must emit `failure`, `trace`, `suspected_files`, `impact`, `safe_patch_scope`, `confidence`, `notes` |
| Mock/demo mode | Always static | `--mock` must remain byte-compatible with today's demo |

## 5. Compatibility requirements for the replacement

1. Keep `get_context_for_failure(failure_log: str) -> dict` as the public method.
2. Return a dict containing at least `failure{type,message}`, `trace[]`,
   `suspected_files[]`, `impact[]`, `safe_patch_scope[]`, `confidence`, `notes`.
3. All file paths must be project-root-relative and within the risk gate's
   `allowed_prefixes` (`demo_app/app/`, `demo_app/tests/`).
4. `--mock` must return the static JSON **untouched** so the recorded demo stays
   byte-for-byte identical.
5. Real mode must not *require* the static JSON; it is only a fallback.

The replacement implementation lives in `agent/lynkmesh_adapter.py` (rewritten) plus a new
`agent/context_builder.py` that maps the LynkMesh graph onto the schema above. See
`docs/real_lynkmesh_integration_design.md`.
