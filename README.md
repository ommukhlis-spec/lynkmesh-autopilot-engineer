# LynkMesh Autopilot Engineer

**Self-healing codebase agent powered by Qwen and deterministic graph context.**

LynkMesh Autopilot Engineer is a hackathon-grade autonomous remediation workflow for PHP codebases. It reads a CI/test failure, retrieves deterministic route-controller-service-model context from LynkMesh, asks Qwen to generate a safe patch plan, applies the patch inside a restricted boundary, runs tests, self-corrects when the first fix fails, and produces a human-reviewable remediation report.

This project is intentionally scoped as a **production-minded prototype**, not a production auto-deployer. It does not merge or deploy changes automatically. All fixes are prepared for maintainer review.

## Why it matters

LLMs can generate code, but they often lack reliable understanding of a real codebase structure. LynkMesh adds deterministic codebase context: routes, controllers, services, models, impacted files, and safe patch scope. Qwen then turns that grounded context into actionable patch proposals that are verified by tests.

## What it demonstrates

The demo app contains two intentional issues:

1. `TransactionService` calls `getMontlySummary()` instead of `getMonthlySummary()`.
2. `TransactionModel` returns `amount_total`, while the route contract/test expects `total_amount`.

The Autopilot flow demonstrates:

```text
failure detected
→ LynkMesh deterministic trace loaded
→ Qwen patch attempt 1 generated
→ patch applied safely
→ test still fails
→ self-correction loop starts
→ Qwen patch attempt 2 generated
→ final test passes
→ human-reviewable report generated
```

## Architecture

```text
CI/Test Failure
      ↓
Autopilot Orchestrator
      ↓
LynkMesh Context Adapter
      ↓
Qwen Cloud Reasoning
      ↓
Safe Patch Engine + Risk Gate
      ↓
Test Runner
      ↓
Self-Correction Loop
      ↓
Human-Reviewable Report / PR Summary
```

## Project structure

```text
agent/                 Autopilot orchestration and safety components
demo_app/              Small PHP app with intentional test failures
docs/                  Architecture, demo script, and submission notes
deploy/                Docker and Alibaba Cloud deployment notes
runs/                  Sample failure/context files and runtime output
web/                   Flask dashboard for demo visualization
```

## Requirements

- Python 3.10+
- PHP CLI available as `php`
- Qwen Cloud / Alibaba Model Studio API key for real mode
- Git and Docker are optional but recommended

## Quick start: deterministic demo mode

Use this for repeatable video recording.

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
python -m agent.main --mock
```

Expected output:

```text
[DEMO RESET] restored broken baseline files=2
[TEST BEFORE] failed
[LYNKMESH CONTEXT] loaded
[QWEN PATCH] generated attempt=1
[PATCH] applied attempt=1 files=1
[TEST AFTER attempt=1] failed
[SELF-CORRECTION] starting retry
[QWEN PATCH] generated attempt=2
[PATCH] applied attempt=2 files=1
[TEST AFTER attempt=2] passed
[REPORT] runs/latest/remediation_report.md
```

## Run with real Qwen Cloud API

Copy the example environment file:

```bash
copy .env.example .env
```

For Windows PowerShell, edit `.env` with Notepad:

```powershell
notepad .env
```

Fill in your workspace endpoint and API key:

```env
MOCK_QWEN=false
QWEN_API_KEY=your_qwen_or_dashscope_key
QWEN_BASE_URL=https://ws-xxxxx.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
QWEN_TIMEOUT_SECONDS=60
```

Then run:

```bash
python -m agent.main
```

Real mode sends the failure log, LynkMesh deterministic context, retry feedback, and safe file contents to Qwen. Qwen returns a structured patch-plan JSON. The existing risk gate and patch engine still validate the response before any file is modified.

## Run dashboard

After running the agent:

```bash
python web/app.py
```

Open:

```text
http://127.0.0.1:8080
```

Useful endpoints:

```text
GET  /health
GET  /runs/latest
POST /autopilot/run?mock=true
POST /autopilot/run?mock=false
GET  /
```

The dashboard includes buttons to run either deterministic mock mode or real Qwen mode. For cloud deployment proof, `/health` demonstrates the service is live and `/autopilot/run?mock=false` demonstrates Qwen-backed execution when credentials are configured.

## Safety guardrails

The prototype includes these safety controls:

- Allowed patch scope is restricted to demo application files.
- Sensitive paths such as `.env`, `vendor/`, `deploy/`, secrets, credentials, and private keys are blocked.
- Patch plans with too many file edits are rejected.
- Test verification is required before a run is marked as passed.
- Human approval is required before merge or deployment.

## Qwen usage

Qwen is used for:

- reasoning over failure logs and LynkMesh context;
- generating patch-plan JSON;
- using test failure feedback for self-correction;
- creating human-reviewable remediation summaries.

The `--mock` mode exists only to make the demo deterministic and repeatable. The real integration is implemented in `agent/qwen_client.py` using the OpenAI-compatible Qwen Cloud endpoint.

## LynkMesh usage

LynkMesh provides deterministic codebase context, including:

- failure classification;
- route-controller-service-model trace;
- suspected files;
- safe patch scope;
- impacted features.

The adapter invokes **LynkMesh Open directly**. In real mode (`python -m agent.main`, no
`--mock`) it scans the configured repository (`demo_app/` by default; override with
`--repo`) using `lynkmesh pack --profile expanded` + `lynkmesh report`, maps the failure onto
the call graph, and emits a provenance-tagged context (`source=lynkmesh_real`). Install
LynkMesh Open and ensure `php` is on PATH:

```bash
pip install -e ../lynkmesh-open
```

`--mock` keeps the deterministic demo using `runs/sample_lynkmesh_context.json` with
unchanged output for video recording. `--mock-qwen` runs the real LynkMesh scan with
deterministic (mock) Qwen — useful for verifying the real context path without API cost. If
LynkMesh or PHP is unavailable in real mode, the adapter falls back to the static JSON,
tagged `source=static_fallback`. See `docs/real_lynkmesh_integration_design.md` and
`docs/lynkmesh_capabilities.md`.

## Limitations

- Current demo is PHP-first.
- Current scenario focuses on route/controller/service/model remediation.
- The agent does not deploy to production.
- Generated patches require human review.
- Broader language/framework support is future work.

## What's next

- GitHub PR creation.
- GitHub Actions integration.
- Laravel support.
- Better multi-file impact analysis.
- Human approval UI.
- Security scanning before patch submission.
- Incident alert ingestion.

## License

MIT


## Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for common local run issues.
