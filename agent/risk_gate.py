from __future__ import annotations

from pathlib import Path
from .config import AgentConfig


class RiskGate:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def validate_file_path(self, relative_file: str) -> None:
        normalized = relative_file.replace("\\", "/")

        if any(fragment in normalized for fragment in self.config.blocked_fragments):
            raise ValueError(f"Blocked unsafe patch target: {relative_file}")

        if not any(normalized.startswith(prefix) for prefix in self.config.allowed_prefixes):
            raise ValueError(f"Patch target is outside allowed scope: {relative_file}")

        resolved = (self.config.root_dir / relative_file).resolve()
        if not str(resolved).startswith(str(self.config.root_dir.resolve())):
            raise ValueError(f"Path traversal attempt blocked: {relative_file}")

    def validate_patch_plan(self, patch_plan: dict) -> None:
        edits = patch_plan.get("edits", [])
        if not edits:
            raise ValueError("Patch plan has no edits.")
        if len(edits) > 3:
            raise ValueError("Patch plan modifies too many files for this demo guardrail.")
        for edit in edits:
            self.validate_file_path(edit["file"])
