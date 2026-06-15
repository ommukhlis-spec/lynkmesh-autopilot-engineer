# Submission Notes

## Track

Autopilot Agent

## Project title

LynkMesh Autopilot Engineer

## Short tagline

Self-healing codebase agent powered by Qwen and deterministic graph context.

## Existing or new project

Existing.

LynkMesh existed before the hackathon as an early research project focused on deterministic codebase context and graph-based retrieval. During the submission period, we built the hackathon-specific Autopilot Engineer execution layer: Qwen integration, patch planning, test execution, self-correction loop, risk gate, report generation, dashboard, and deployment path.

## AI tools leveraged

We leveraged Qwen and Qwen Cloud API as the core AI layer for reasoning, patch generation, and autonomous remediation decisions. We also used ChatGPT during development for planning, architecture refinement, documentation drafting, demo scripting, and improving the Devpost submission narrative.

LynkMesh itself provides deterministic codebase context and graph-based analysis, while Qwen is used to turn that context into actionable patch proposals, test-driven self-correction, and human-reviewable remediation reports.

## Demo evidence to capture

- Terminal real Qwen run.
- Dashboard status passed.
- Timeline showing attempt 1 failed and attempt 2 passed.
- Human-reviewable remediation report.
- `agent/qwen_client.py` showing Qwen integration.
- Alibaba Cloud deployment endpoint `/health`.
- Alibaba Cloud deployment endpoint `/runs/latest`.

## Claim boundaries

Do not claim this is a universal production autonomous engineer. Say it is a production-minded prototype for PHP remediation with human approval.
