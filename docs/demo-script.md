# 3-Minute Demo Script

## 0:00–0:20 — Problem

Modern CI failures often require developers to manually trace routes, controllers, services, models, and tests before they can safely fix the issue. Generic coding assistants can suggest code, but they do not always know the structure and impact of the codebase.

## 0:20–0:45 — Solution

LynkMesh Autopilot Engineer combines Qwen with deterministic codebase context. LynkMesh provides the code trace and safe patch scope. Qwen generates a patch plan. The agent applies it safely, runs tests, and self-corrects if verification fails.

## 0:45–1:35 — Run the Agent

Show terminal:

```bash
python -m agent.main
```

Narration:

The agent resets the demo app to a known broken state, runs the baseline test, detects the failure, loads LynkMesh context, and asks Qwen to generate the first patch.

## 1:35–2:10 — Unhappy Path and Self-Correction

Show:

```text
[TEST AFTER attempt=1] failed
[SELF-CORRECTION] starting retry
[QWEN PATCH] generated attempt=2
[TEST AFTER attempt=2] passed
```

Narration:

The first patch fixes the visible undefined method error, but the test reveals a second response-contract mismatch. The agent uses that failure feedback to generate a second patch and passes verification.

## 2:10–2:45 — Dashboard and Report

Show dashboard:

- status passed;
- Qwen mode/model;
- attempt 1 failed;
- attempt 2 passed;
- LynkMesh trace;
- human-reviewable report.

Narration:

The output is not an automatic production deployment. It is a safe, human-reviewable remediation report with root cause, changed files, test results, risk analysis, and approval status.

## 2:45–3:00 — Closing

LynkMesh Autopilot Engineer turns CI failures into safe, verified, human-reviewable fixes by combining Qwen reasoning with deterministic codebase graph context.
