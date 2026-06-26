from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

# Allow `python agent/main.py` and `python -m agent.main`.
if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent.config import default_config
from agent.orchestrator import AutopilotOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LynkMesh Autopilot Engineer starter workflow.")
    parser.add_argument("--mock", action="store_true", help="Deterministic demo: mock Qwen + static LynkMesh context.")
    parser.add_argument(
        "--mock-qwen",
        action="store_true",
        help="Force mock Qwen patch generation (default follows --mock). Enables real-LynkMesh + mock-Qwen for evaluation.",
    )
    parser.add_argument(
        "--mock-context",
        action="store_true",
        help="Force static LynkMesh context (default follows --mock).",
    )
    parser.add_argument("--repo", type=Path, default=None, help="Repository path to scan with LynkMesh (default: demo_app).")
    parser.add_argument("--lynkmesh-timeout", type=float, default=None, help="LynkMesh scan timeout in seconds.")
    parser.add_argument("--no-fallback", action="store_true", help="Disable fallback to static context on LynkMesh failure.")
    args = parser.parse_args()

    config = default_config()
    overrides: dict = {}
    if args.repo is not None:
        overrides["lynkmesh_repo_path"] = args.repo
    if args.lynkmesh_timeout is not None:
        overrides["lynkmesh_timeout"] = args.lynkmesh_timeout
    if args.no_fallback:
        overrides["lynkmesh_fallback_to_static"] = False
    if overrides:
        config = dataclasses.replace(config, **overrides)

    mock_qwen = args.mock or args.mock_qwen
    mock_context = args.mock or args.mock_context

    orchestrator = AutopilotOrchestrator(config=config, mock_qwen=mock_qwen, mock_context=mock_context)
    result = orchestrator.run()
    return 0 if result.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
