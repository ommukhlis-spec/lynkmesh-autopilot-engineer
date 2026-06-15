from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReportWriter:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self.latest_dir = runs_dir / "latest"
        self.latest_dir.mkdir(parents=True, exist_ok=True)

    def write(self, payload: dict[str, Any]) -> Path:
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()

        json_path = self.latest_dir / "run.json"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        report = self._to_markdown(payload)
        report_path = self.latest_dir / "remediation_report.md"
        report_path.write_text(report, encoding="utf-8")
        return report_path

    def _redact_local_paths(self, text: str) -> str:
        """Keep public reports clean when tests print absolute local paths."""
        if not text:
            return text
        text = re.sub(r"[A-Za-z]:\\[^\n\r:]+", "<local_path>", text)
        text = re.sub(r"/home/[^\n\r:]+", "<local_path>", text)
        text = re.sub(r"/Users/[^\n\r:]+", "<local_path>", text)
        return text

    def _to_markdown(self, payload: dict[str, Any]) -> str:
        context = payload.get("context", {})
        before = payload.get("test_before", {})
        after = payload.get("test_after", {})
        changed = payload.get("changed_files", [])
        attempts = payload.get("attempts", [])
        final_patch = payload.get("patch_plan", {})

        lines = [
            "# Autopilot Remediation Report",
            "",
            "## AI Execution",
            f"Qwen mode: {payload.get('qwen_mode', 'unknown')}",
            f"Qwen model: {payload.get('qwen_model', 'unknown')}",
            "LynkMesh context: deterministic route-controller-service-model trace",
            "Human approval: required before merge or deployment",
            "",
            "## Failure",
            context.get("failure", {}).get("message", "Unknown failure"),
            "",
            "## LynkMesh Trace",
        ]
        lines.extend([f"- {item}" for item in context.get("trace", [])])
        lines.extend([
            "",
            "## Autopilot Attempts",
        ])

        for attempt in attempts:
            patch = attempt.get("patch_plan", {})
            test = attempt.get("test_result", {})
            lines.extend([
                f"### Attempt {attempt.get('attempt')}",
                f"Patch summary: {patch.get('summary', 'No patch summary.')}",
                f"Risk level: {patch.get('risk', 'unknown')}",
                f"Self-correction: {'yes' if patch.get('self_correction') else 'no'}",
                "Changed files:",
            ])
            lines.extend([f"- {item}" for item in attempt.get("changed_files", [])] or ["- None"])
            lines.extend([
                f"Test result: {'passed' if test.get('passed') else 'failed'}",
            ])
            if not test.get("passed"):
                output = self._redact_local_paths(test.get("output", "").strip())
                if output:
                    lines.extend([
                        "Failure feedback used for next attempt:",
                        "```text",
                        output[-1200:],
                        "```",
                    ])
            lines.append("")

        lines.extend([
            "## Final Patch Summary",
            final_patch.get("summary", "No patch summary."),
            "",
            "## Changed Files",
        ])
        lines.extend([f"- {item}" for item in changed] or ["- None"])
        lines.extend([
            "",
            "## Risk Analysis",
            f"Final risk level: {final_patch.get('risk', 'unknown')}",
            "Patch plans were validated against allowed file boundaries before being applied.",
            "Sensitive paths such as .env, vendor/, deploy/, secrets, credentials, and private keys are blocked.",
            "",
            "## Verification",
            f"Before: {'passed' if before.get('passed') else 'failed'}",
            f"Final after self-correction: {'passed' if after.get('passed') else 'failed'}",
            "",
            "## Human Approval",
            "Ready for maintainer review. No production deployment was performed automatically.",
        ])
        return "\n".join(lines) + "\n"
