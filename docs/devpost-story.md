# Devpost Project Story

## Inspiration

Modern software teams lose a lot of time debugging broken builds, tracing code dependencies, and figuring out which files are safe to change. Large language models are powerful at generating code, but they often lack deterministic understanding of a real codebase structure. They may suggest fixes without knowing the route, controller, service, model, database, and test relationships behind the failure.

LynkMesh Autopilot Engineer was inspired by a simple question: can an AI agent move beyond giving advice and actually help repair a broken software workflow safely?

Instead of building another coding chatbot, we wanted to create an autonomous remediation workflow that combines Qwen's reasoning ability with LynkMesh's deterministic codebase graph context. The goal is not to replace developers, but to reduce debugging time, make fixes safer, and turn CI failures into human-reviewable patches.

## What it does

LynkMesh Autopilot Engineer is a self-healing software engineering agent for PHP codebases.

When a test or CI failure occurs, the agent reads the failure log, uses LynkMesh to trace the affected code path, identifies related routes/controllers/services/models, sends the failure and deterministic context to Qwen, generates a safe patch proposal, applies the patch inside a restricted file boundary, runs tests again, self-corrects if verification fails, and produces a remediation report for human approval.

## How we built it

We built the project as an execution layer on top of LynkMesh. LynkMesh acts as the deterministic context provider, while Qwen generates patch plans from failure logs, code snippets, retry feedback, and graph context.

The system includes an orchestrator, LynkMesh adapter, Qwen client, patch engine, test runner, risk gate, report writer, and lightweight Flask dashboard.

For the demo, we focused on a PHP route-controller-service-model failure scenario. This allowed us to show a complete end-to-end flow without overclaiming support for every language or every type of bug.

## Challenges we ran into

The biggest challenge was turning LynkMesh from a context layer into a true Autopilot workflow. A context provider can explain what might be wrong, but an Autopilot agent must take action: generate code, apply patches, run tests, handle failure, and stop safely when human approval is needed.

Another challenge was safety. Autonomous code modification can be risky, so we added guardrails such as restricted patch scope, blocked sensitive files, limited retries, and human approval checkpoints.

## Accomplishments that we're proud of

We are proud that LynkMesh Autopilot Engineer is more than a chatbot or code suggestion tool. It demonstrates an actual autonomous remediation loop.

The project shows how deterministic graph-based context can make AI coding agents more grounded. Instead of relying only on vector search or generic code completion, the agent uses structural codebase relationships to understand where a failure happened and what files may be impacted.

We are also proud of the safety-first design. The agent does not blindly modify the whole repository or deploy changes directly to production. It works within a controlled boundary, verifies changes with tests, and produces a transparent report for developers to review.

## What we learned

We learned that autonomous agents need more than language model reasoning. They need reliable context, tool boundaries, verification steps, and recovery mechanisms.

Qwen can generate useful fixes, but the quality of the result improves significantly when the model receives structured context from LynkMesh instead of raw logs alone. The graph-based context helps narrow the problem, reduce irrelevant changes, and make the generated patch easier to review.

## What's next for LynkMesh Autopilot Engineer

Next, we want to expand LynkMesh Autopilot Engineer from a focused PHP demo into a broader engineering workflow platform: GitHub PR creation, GitHub Actions integration, Laravel support, better multi-file impact analysis, more advanced self-correction strategies, human approval UI, and support for JavaScript and Python codebases.

## Built with

Qwen, Qwen Cloud API, Alibaba Cloud, Python, PHP, Flask, LynkMesh, MCP-style tool integration, JSON-based codebase context, Git, Docker, HTML/CSS, JavaScript, and Markdown report generation.
