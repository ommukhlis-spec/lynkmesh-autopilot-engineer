"""LynkMesh context adapter.

Real mode invokes LynkMesh Open directly (``lynkmesh pack`` + ``lynkmesh report``) on a
configurable repository path, parses the deterministic graph, and hands it to
:mod:`agent.context_builder` to produce targeted context for Qwen. Mock/demo mode loads
the static ``sample_lynkmesh_context.json`` untouched so the recorded demo stays
byte-for-byte deterministic. If LynkMesh cannot run, real mode falls back to the static
JSON (tagged) so the workflow still completes.

Design notes:
* LynkMesh is invoked as an isolated subprocess with ``PYTHONHASHSEED=0`` (the LynkMesh
  pipeline refuses to run otherwise) and a timeout.
* No paths are hardcoded: the repo path, timeout, profile, and binary are all configurable.
* Structured status is emitted as ``[LYNKMESH SCAN] key=value`` lines and a ``provenance``
  block is attached to the returned context.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .context_builder import ContextBuilder


class LynkMeshAdapter:
    """Produces remediation context, either from a real LynkMesh scan or static JSON."""

    def __init__(
        self,
        repo_path: Path,
        *,
        mock: bool = False,
        context_path: Path | None = None,
        root_dir: Path | None = None,
        allowed_prefixes: tuple[str, ...] = (),
        timeout: float = 120.0,
        profile: str = "expanded",
        fallback_to_static: bool = True,
        lynkmesh_bin: str | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.mock = mock
        self.context_path = Path(context_path) if context_path else None
        self.root_dir = Path(root_dir) if root_dir else self.repo_path
        self.allowed_prefixes = allowed_prefixes
        self.timeout = timeout
        self.profile = profile
        self.fallback_to_static = fallback_to_static
        self.lynkmesh_bin = lynkmesh_bin

    # ----------------------------------------------------------------- public

    def get_context_for_failure(self, failure_log: str) -> dict[str, Any]:
        """Return remediation context for a CI failure log.

        Signature is unchanged from the original static loader, so the orchestrator
        needs no flow changes.
        """
        if self.mock:
            # Demo mode: return the static JSON untouched (byte-compatible).
            # The orchestrator prints the "[LYNKMESH CONTEXT] loaded" line.
            return self._load_static()

        self._log("repo=%s timeout=%s profile=%s", self.repo_path, self.timeout, self.profile)
        try:
            pack = self._run_lynkmesh(["pack", str(self.repo_path), "--profile", self.profile, "--quiet"])
            report = self._run_lynkmesh(["report", str(self.repo_path), "--quiet"], required=False)
        except Exception as exc:  # noqa: BLE001 - any failure triggers fallback
            return self._handle_failure(exc)

        try:
            context = ContextBuilder.build(
                report=report,
                pack=pack,
                failure_log=failure_log,
                repo_path=self.repo_path,
                root_dir=self.root_dir,
                allowed_prefixes=self.allowed_prefixes,
            )
        except Exception as exc:  # noqa: BLE001 - context build failure triggers fallback
            return self._handle_failure(exc)

        prov = context.get("provenance", {})
        self._log(
            "ok source=lynkmesh_real nodes=%s edges=%s calls=%s build_id=%s",
            prov.get("graph_facts", {}).get("node_count"),
            prov.get("graph_facts", {}).get("edge_count"),
            prov.get("calls_confirmed_count"),
            (prov.get("build_id") or "")[:8],
        )
        return context

    # -------------------------------------------------------------- internals

    def _run_lynkmesh(self, args: list[str], required: bool = True) -> dict[str, Any] | None:
        binary = self.lynkmesh_bin or shutil.which("lynkmesh")
        if not binary:
            raise RuntimeError(
                "lynkmesh CLI not found on PATH. Install LynkMesh Open "
                "(pip install -e <path>/lynkmesh-open) or use --mock."
            )
        if not shutil.which("php"):
            raise RuntimeError(
                "php executable not found on PATH. LynkMesh's PHP bridge requires the PHP CLI."
            )
        if not self.repo_path.is_dir():
            raise FileNotFoundError(f"LynkMesh scan target is not a directory: {self.repo_path}")

        # PYTHONHASHSEED=0 is mandatory for LynkMesh's determinism guard.
        env = {**os.environ, "PYTHONHASHSEED": "0"}
        try:
            proc = subprocess.run(
                [binary, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"lynkmesh {' '.join(args[:1])} timed out after {self.timeout}s") from exc

        if proc.returncode != 0:
            if not required:
                self._log("warn command=%s nonfatal exit=%s", args[0], proc.returncode)
                return None
            detail = (proc.stderr or "").strip().splitlines()
            detail_str = detail[-1] if detail else f"exit code {proc.returncode}"
            raise RuntimeError(f"lynkmesh {args[0]} failed: {detail_str}")

        stdout = (proc.stdout or "").strip()
        if not stdout:
            if not required:
                return None
            raise RuntimeError(f"lynkmesh {args[0]} produced no JSON output")
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"lynkmesh {args[0]} returned non-JSON output: {exc}") from exc

    def _handle_failure(self, exc: Exception) -> dict[str, Any]:
        reason = f"{type(exc).__name__}: {exc}"
        self._log("failed reason=%s fallback_to_static=%s", reason, self.fallback_to_static)
        if not self.fallback_to_static:
            raise RuntimeError(f"LynkMesh scan failed and fallback disabled: {reason}") from exc
        if not self.context_path or not self.context_path.exists():
            raise RuntimeError(
                f"LynkMesh scan failed and no static fallback available: {reason}"
            ) from exc
        context = self._load_static()
        context["provenance"] = {
            "source": "static_fallback",
            "fallback_reason": reason,
            "scan_path": str(self.repo_path),
        }
        self._log("fallback=static reason=%s", type(exc).__name__)
        return context

    def _load_static(self) -> dict[str, Any]:
        if not self.context_path or not self.context_path.exists():
            raise FileNotFoundError(f"LynkMesh context not found: {self.context_path}")
        return json.loads(self.context_path.read_text(encoding="utf-8"))

    @staticmethod
    def _log(message: str, *args: Any) -> None:
        rendered = message % args if args else message
        print(f"[LYNKMESH SCAN] {rendered}")
