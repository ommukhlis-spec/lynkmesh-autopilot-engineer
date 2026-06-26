from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentConfig:
    root_dir: Path
    demo_app_dir: Path
    runs_dir: Path
    failure_log: Path
    context_json: Path
    # LynkMesh Open integration (real context mode). The adapter scans
    # `lynkmesh_repo_path` and builds context dynamically from the graph.
    lynkmesh_repo_path: Path = Path("demo_app")
    lynkmesh_timeout: float = 120.0
    lynkmesh_profile: str = "expanded"
    lynkmesh_fallback_to_static: bool = True
    max_retries: int = 2
    allowed_prefixes: tuple[str, ...] = (
        "demo_app/app/",
        "demo_app/tests/",
    )
    blocked_fragments: tuple[str, ...] = (
        ".env",
        "vendor/",
        "deploy/",
        "secrets",
        "credential",
        "private_key",
    )


def default_config() -> AgentConfig:
    root = Path(__file__).resolve().parents[1]
    return AgentConfig(
        root_dir=root,
        demo_app_dir=root / "demo_app",
        runs_dir=root / "runs",
        failure_log=root / "runs" / "sample_failure.log",
        context_json=root / "runs" / "sample_lynkmesh_context.json",
        lynkmesh_repo_path=root / "demo_app",
    )
