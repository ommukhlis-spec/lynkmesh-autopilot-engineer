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
    )
