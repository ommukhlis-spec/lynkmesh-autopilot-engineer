from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python agent/main.py` and `python -m agent.main`.
if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent.config import default_config
from agent.orchestrator import AutopilotOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LynkMesh Autopilot Engineer starter workflow.")
    parser.add_argument("--mock", action="store_true", help="Use mock Qwen patch generation.")
    args = parser.parse_args()

    config = default_config()
    orchestrator = AutopilotOrchestrator(config=config, mock_qwen=args.mock)
    result = orchestrator.run()
    return 0 if result.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
