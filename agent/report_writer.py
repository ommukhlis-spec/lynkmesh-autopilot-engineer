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
        json_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        report = self._to_markdown(payload)

        report_path = self.latest_dir / "remediation_report.md"
        report_path.write_text(report, encoding="utf-8")

        return report_path

    def _redact_local_paths(self, text: str) -> str:
        """Remove local filesystem paths from public reports."""
        if not text:
            return text

        text = re.sub(r"[A-Za-z]:\\[^\n\r:]+", "<local_path>", text)
        text = re.sub(r"/home/[^\n\r:]+", "<local_path>", text)
        text = re.sub(r"/Users/[^\n\r:]+", "<local_path>", text)

        return text

    def _render_lynkmesh_section(
        self,
        provenance: dict[str, Any],
    ) -> list[str]:
        source = provenance.get("source", "unknown")

        graph = provenance.get("graph_facts", {})

        lines = [
            "## LynkMesh Context",
            f"Source: {source}",
        ]

        if provenance.get("build_id"):
            lines.append(f"Build ID: {provenance['build_id']}")

        if provenance.get("scan_path"):
            lines.append(f"Scan Path: {provenance['scan_path']}")

        node_count = graph.get("node_count")
        edge_count = graph.get("edge_count")

        if node_count is not None:
            lines.append(f"Graph Nodes: {node_count}")

        if edge_count is not None:
            lines.append(f"Graph Edges: {edge_count}")

        calls = provenance.get("calls_confirmed_count")
        if calls is not None:
            lines.append(f"Confirmed Calls: {calls}")

        if provenance.get("fallback_reason"):
            lines.extend(
                [
                    "",
                    "**Fallback Reason**",
                    provenance["fallback_reason"],
                ]
            )

        lines.append("")

        return lines

    def _to_markdown(self, payload: dict[str, Any]) -> str:
        context = payload.get("context", {})

        before = payload.get("test_before", {})
        after = payload.get("test_after", {})

        changed = payload.get("changed_files", [])
        attempts = payload.get("attempts", [])

        final_patch = payload.get("patch_plan", {})

        provenance = context.get("provenance", {})

        lines = [
            "# Autopilot Remediation Report",
            "",
            "## AI Execution",
            f"Qwen mode: {payload.get('qwen_mode', 'unknown')}",
            f"Qwen model: {payload.get('qwen_model', 'unknown')}",
            "Human approval: required before merge or deployment",
            "",
        ]

        lines.extend(self._render_lynkmesh_section(provenance))

        lines.extend(
            [
                "## Failure",
                context.get("failure", {}).get(
                    "message",
                    "Unknown failure",
                ),
                "",
                "## LynkMesh Trace",
            ]
        )

        trace = context.get("trace", [])

        if trace:
            lines.extend([f"- {item}" for item in trace])
        else:
            lines.append("- No trace available")

        lines.extend(
            [
                "",
                "## Autopilot Attempts",
            ]
        )

        for attempt in attempts:
            patch = attempt.get("patch_plan", {})
            test = attempt.get("test_result", {})

            lines.extend(
                [
                    f"### Attempt {attempt.get('attempt')}",
                    f"Patch summary: {patch.get('summary', 'No patch summary.')}",
                    f"Risk level: {patch.get('risk', 'unknown')}",
                    f"Self-correction: {'yes' if patch.get('self_correction') else 'no'}",
                    "Changed files:",
                ]
            )

            changed_files = attempt.get("changed_files", [])

            if changed_files:
                lines.extend([f"- {item}" for item in changed_files])
            else:
                lines.append("- None")

            lines.append(
                f"Test result: {'passed' if test.get('passed') else 'failed'}"
            )

            if not test.get("passed"):
                output = self._redact_local_paths(
                    test.get("output", "").strip()
                )

                if output:
                    lines.extend(
                        [
                            "Failure feedback used for next attempt:",
                            "```text",
                            output[-1200:],
                            "```",
                        ]
                    )

            lines.append("")

        lines.extend(
            [
                "## Final Patch Summary",
                final_patch.get(
                    "summary",
                    "No patch summary.",
                ),
                "",
                "## Changed Files",
            ]
        )

        if changed:
            lines.extend([f"- {item}" for item in changed])
        else:
            lines.append("- None")

        lines.extend(
            [
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
            ]
        )

        return "\n".join(lines) + "\n"