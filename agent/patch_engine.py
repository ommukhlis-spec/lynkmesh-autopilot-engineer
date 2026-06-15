from __future__ import annotations

from .config import AgentConfig
from .risk_gate import RiskGate


class PatchEngine:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.risk_gate = RiskGate(config)

    def apply_patch_plan(self, patch_plan: dict) -> list[str]:
        self.risk_gate.validate_patch_plan(patch_plan)
        changed_files: list[str] = []

        for edit in patch_plan["edits"]:
            rel_file = edit["file"]
            target = self.config.root_dir / rel_file
            if not target.exists():
                raise FileNotFoundError(f"Patch target not found: {rel_file}")

            content = target.read_text(encoding="utf-8")
            find = edit["find"]
            replace = edit["replace"]

            if find not in content:
                raise ValueError(f"Could not find expected text in {rel_file}: {find}")

            content = content.replace(find, replace, 1)
            target.write_text(content, encoding="utf-8")
            changed_files.append(rel_file)

        return changed_files
