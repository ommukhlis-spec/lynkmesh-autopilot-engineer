from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LynkMeshAdapter:
    """Starter adapter.

    In the final version, replace this JSON loader with a call to LynkMesh MCP/API.
    """

    def __init__(self, context_path: Path) -> None:
        self.context_path = context_path

    def get_context_for_failure(self, failure_log: str) -> dict[str, Any]:
        if not self.context_path.exists():
            raise FileNotFoundError(f"LynkMesh context not found: {self.context_path}")
        return json.loads(self.context_path.read_text(encoding="utf-8"))
