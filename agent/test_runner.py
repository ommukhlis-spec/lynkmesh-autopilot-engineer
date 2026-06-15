from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    passed: bool
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


class TestRunner:
    def __init__(self, demo_app_dir: Path) -> None:
        self.demo_app_dir = demo_app_dir

    def run(self) -> TestResult:
        proc = subprocess.run(
            ["php", "tests/run.php"],
            cwd=self.demo_app_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return TestResult(
            passed=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
