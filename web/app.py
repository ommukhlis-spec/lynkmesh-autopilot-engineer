from __future__ import annotations

import json
from pathlib import Path
import os
import sys
from flask import Flask, jsonify, redirect, render_template, request, url_for

ROOT = Path(__file__).resolve().parents[1]
# When this file is launched as `python web/app.py`, Python puts `web/`
# on sys.path instead of the project root. Add the root explicitly so Flask
# endpoints can import the local `agent` package reliably on Windows, Docker,
# and Alibaba Cloud.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUN_JSON = ROOT / "runs" / "latest" / "run.json"
REPORT = ROOT / "runs" / "latest" / "remediation_report.md"

app = Flask(__name__)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@app.get("/health")
def health():
    return jsonify({"status": "ok", "app": "lynkmesh-autopilot-engineer"})


@app.get("/runs/latest")
def latest_json():
    if not RUN_JSON.exists():
        return jsonify({"status": "not_found", "message": "Run the agent first."}), 404
    return jsonify(json.loads(RUN_JSON.read_text(encoding="utf-8")))


@app.post("/autopilot/run")
def run_autopilot():
    # Browser-friendly endpoint for demos and cloud proof.
    # mock=true keeps the demo deterministic; mock=false uses Qwen Cloud credentials from .env/environment.
    from agent.config import default_config
    from agent.orchestrator import AutopilotOrchestrator

    env_default_mock = _parse_bool(os.getenv("MOCK_QWEN"), default=False)
    mock = _parse_bool(request.args.get("mock"), default=env_default_mock)
    config = default_config()
    orchestrator = AutopilotOrchestrator(config=config, mock_qwen=mock)
    payload = orchestrator.run()

    if request.headers.get("Accept", "").startswith("application/json"):
        return jsonify(payload)
    return redirect(url_for("dashboard"))


@app.get("/")
def dashboard():
    report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else "Run the agent first."
    data = json.loads(RUN_JSON.read_text(encoding="utf-8")) if RUN_JSON.exists() else {}
    attempts = data.get("attempts", []) if isinstance(data, dict) else []
    passed_attempts = [a for a in attempts if a.get("test_result", {}).get("passed")]
    metrics = {
        "attempts": len(attempts),
        "changed_files": len(data.get("changed_files", [])) if isinstance(data, dict) else 0,
        "self_correction": any(a.get("patch_plan", {}).get("self_correction") for a in attempts),
        "final_passed": bool(data.get("test_after", {}).get("passed")) if isinstance(data, dict) else False,
        "first_passed_attempt": passed_attempts[0].get("attempt") if passed_attempts else None,
    }
    return render_template("dashboard.html", report=report, data=data, metrics=metrics)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
