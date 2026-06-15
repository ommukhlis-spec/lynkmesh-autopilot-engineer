# Architecture

LynkMesh Autopilot Engineer is built around one narrow but complete autonomous remediation loop.

```text
CI/Test Failure
      ↓
Autopilot Orchestrator
      ↓
LynkMesh Context Adapter
      ↓
Qwen Cloud Reasoning
      ↓
Safe Patch Engine
      ↓
Risk Gate
      ↓
Test Runner
      ↓
Self-Correction Loop
      ↓
Human-Reviewable Report
```

## Components

### Autopilot Orchestrator

Controls the full workflow: reset demo state, run baseline tests, retrieve context, ask Qwen for a patch plan, apply the patch, run tests, retry if needed, and generate the report.

### LynkMesh Context Adapter

Loads deterministic codebase context. For this hackathon prototype, the context is represented as JSON with failure type, trace, suspected files, impact, and safe patch scope.

### Qwen Client

Uses Qwen Cloud through an OpenAI-compatible endpoint. The model receives failure logs, LynkMesh trace, retry feedback, and safe file contents. It must return a structured JSON patch plan.

### Patch Engine

Applies exact `find`/`replace` edits from the patch plan. It does not execute arbitrary code from the model.

### Risk Gate

Rejects unsafe edits before patching. It blocks sensitive files, path traversal, deployment files, and overly broad patch plans.

### Test Runner

Runs the PHP test command and captures output for verification and self-correction.

### Report Writer

Generates `runs/latest/remediation_report.md` and `runs/latest/run.json` for dashboard visualization and human review.

## Why deterministic context matters

Without LynkMesh, a model only sees a failure log and raw snippets. With LynkMesh, the agent receives the structural path of the failure and the allowed repair boundary. This reduces irrelevant edits and makes the generated patch easier to audit.
