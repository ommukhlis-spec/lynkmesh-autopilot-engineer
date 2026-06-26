"""Turn a LynkMesh graph scan into a compact, targeted context payload for Qwen.

LynkMesh Open produces a *whole-project* deterministic graph (MeshContext Report +
AI Context Pack). It does not take a failure signature and return a targeted trace.
This module is the bridge: it maps a CI failure onto the scanned graph and emits the
same context schema the orchestrator, Qwen client, and report writer already consume
(``failure``, ``trace``, ``suspected_files``, ``impact``, ``safe_patch_scope``,
``confidence``, ``notes``), plus a ``provenance`` block and a compact ``graph_evidence``
digest.

The chain (route -> controller -> service -> model) is derived from the expanded pack's
``calls_confirmed`` edges, not from the failure log's own trace, so the context reflects
real graph analysis rather than a scripted stack trace.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_REDACTED = "__unsafe_redacted__"

# Failure-log parsing patterns.
_FAIL_LINE = re.compile(r"^\s*FAIL:\s*(.+?)\s*$", re.IGNORECASE)
_ROUTE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)")
# Class::method  or  $obj->method  or  Class->method
_SYMBOL = re.compile(r"([A-Za-z_][\w]*)\s*(?:::|->)\s*([A-Za-z_][\w]*)")


def _failure_type(message: str) -> str:
    m = message.lower()
    if "undefined method" in m:
        return "undefined_method"
    if "undefined array key" in m:
        return "undefined_array_key"
    if "undefined variable" in m:
        return "undefined_variable"
    if "undefined constant" in m:
        return "undefined_constant"
    if "assertion failed" in m or "assert" in m:
        return "assertion_failed"
    if "class" in m and "not found" in m:
        return "missing_class"
    return "unknown"


def _parse_failure_log(failure_log: str) -> dict[str, Any]:
    """Extract the failure message, type, called symbol, and route from a CI log."""
    message = ""
    for line in failure_log.splitlines():
        match = _FAIL_LINE.match(line)
        if match:
            message = match.group(1).strip()
            break
    if not message:
        message = next((ln.strip() for ln in failure_log.splitlines() if ln.strip()), "Unknown failure")

    route_match = _ROUTE.search(failure_log)
    route = (route_match.group(1) + " " + route_match.group(2)) if route_match else None

    symbol_match = _SYMBOL.search(message) or _SYMBOL.search(failure_log)
    symbol = None
    called_class = None
    called_method = None
    if symbol_match:
        called_class = symbol_match.group(1)
        called_method = symbol_match.group(2)
        symbol = f"{called_class}::{called_method}"

    return {
        "message": message,
        "type": _failure_type(message),
        "symbol": symbol,
        "called_class": called_class,
        "called_method": called_method,
        "route": route,
    }


def _layer_from_path(path: str) -> str:
    p = (path or "").lower()
    if "controller" in p:
        return "controller"
    if "service" in p:
        return "service"
    if "model" in p:
        return "model"
    if "route" in p:
        return "route"
    if "test" in p:
        return "test"
    return "component"


def _rebase_path(repo_rel: str, repo_path: Path, root_dir: Path) -> str | None:
    """Convert a LynkMesh repo-relative path to a project-root-relative path.

    LynkMesh emits paths relative to the scanned repo (e.g. ``app/Services/X.php``).
    The patch engine and risk gate work relative to the project root, so we prefix
    with ``repo_path`` relative to ``root_dir`` (e.g. ``demo_app/``). No hardcoded
    paths: the prefix is computed from the configured repo path.
    """
    if not repo_rel or repo_rel == _REDACTED or repo_rel.startswith("__"):
        return None
    repo_rel = repo_rel.replace("\\", "/")
    try:
        prefix = Path(repo_path).resolve().relative_to(Path(root_dir).resolve())
    except ValueError:
        prefix = Path("")  # repo is the root or outside it: use LynkMesh path as-is
    if prefix == Path(".") or prefix == Path(""):
        return repo_rel
    return (prefix / repo_rel).as_posix()


def _node_label(node: dict[str, Any]) -> str:
    return node.get("qualified_name") or node.get("label") or node.get("id", "unknown")


def _in_scope(path: str, allowed_prefixes: tuple[str, ...]) -> bool:
    norm = path.replace("\\", "/")
    return any(norm.startswith(prefix) for prefix in allowed_prefixes)


def _dedupe(seq: list[str]) -> list[str]:
    return list(dict.fromkeys(seq))


class ContextBuilder:
    """Map a CI failure onto a LynkMesh graph scan -> targeted context payload."""

    @classmethod
    def build(
        cls,
        report: dict[str, Any] | None,
        pack: dict[str, Any],
        failure_log: str,
        repo_path: Path,
        root_dir: Path,
        allowed_prefixes: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        failure = _parse_failure_log(failure_log)
        evidence = pack.get("evidence_index", {}) or {}
        nodes_by_id: dict[str, dict[str, Any]] = evidence.get("nodes", {}) or {}
        edges = list((evidence.get("edges", {}) or {}).values())

        calls_adj = cls._call_adjacency(edges)
        chain_ids = cls._derive_chain(pack, nodes_by_id, calls_adj)
        chain = cls._chain_nodes(chain_ids, nodes_by_id, repo_path, root_dir)

        trace = cls._build_trace(chain, failure)
        suspected_files = _dedupe([c["root_path"] for c in chain if c["root_path"]])
        safe_patch_scope = cls._safe_patch_scope(chain, failure, allowed_prefixes)
        impact = cls._build_impact(chain, failure)
        confidence = cls._confidence(edges)
        notes = cls._build_notes(chain, failure, confidence)

        context: dict[str, Any] = {
            "failure": {
                "type": failure["type"],
                "message": failure["message"],
                "symbol": failure["symbol"],
                "route": failure["route"],
            },
            "trace": trace,
            "suspected_files": suspected_files,
            "impact": impact,
            "safe_patch_scope": safe_patch_scope,
            "confidence": confidence,
            "notes": notes,
            "graph_evidence": cls._graph_evidence(chain, edges, pack),
            "provenance": cls._provenance(report, pack, repo_path, edges),
        }
        # Tag the source last so the adapter can override it for fallback paths.
        context["provenance"]["source"] = "lynkmesh_real"
        return context

    # ------------------------------------------------------------------ graph

    @staticmethod
    def _call_adjacency(edges: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
        adj: dict[str, list[tuple[str, float]]] = {}
        for edge in edges:
            if edge.get("type") != "calls_confirmed":
                continue
            src = edge.get("source")
            tgt = edge.get("target")
            if not src or not tgt:
                continue
            try:
                conf = float(edge.get("confidence") or 0)
            except (TypeError, ValueError):
                conf = 0.0
            adj.setdefault(src, []).append((tgt, conf))
        return adj

    @staticmethod
    def _derive_chain(
        pack: dict[str, Any],
        nodes_by_id: dict[str, dict[str, Any]],
        calls_adj: dict[str, list[tuple[str, float]]],
    ) -> list[str]:
        """route -> controller -> service -> model via calls_confirmed edges."""
        arch = pack.get("architecture_context", {}) or {}
        entry_candidates = arch.get("entrypoint_candidates", []) or []

        start: str | None = None
        # Prefer an HTTP-entry method that actually calls downstream.
        for cand in entry_candidates:
            cid = cand.get("id")
            if cand.get("type") != "method" or cid not in calls_adj:
                continue
            qname = cand.get("qualified_name", "")
            if not qname.endswith("::__construct"):
                start = cid
                break
        if start is None:
            for cand in entry_candidates:
                cid = cand.get("id")
                if cid in calls_adj:
                    start = cid
                    break
        if start is None:
            # Last resort: any method node with an outgoing call edge.
            for nid, node in nodes_by_id.items():
                if node.get("type") == "method" and nid in calls_adj:
                    start = nid
                    break

        chain: list[str] = []
        visited: set[str] = set()
        cur: str | None = start
        while cur and cur not in visited:
            visited.add(cur)
            chain.append(cur)
            nxt = calls_adj.get(cur)
            cur = nxt[0][0] if nxt else None
        return chain

    @staticmethod
    def _chain_nodes(
        chain_ids: list[str],
        nodes_by_id: dict[str, dict[str, Any]],
        repo_path: Path,
        root_dir: Path,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for cid in chain_ids:
            node = nodes_by_id.get(cid)
            if not node:
                continue
            repo_rel = node.get("path") or ""
            root_path = _rebase_path(repo_rel, repo_path, root_dir)
            if root_path is None:
                continue
            out.append(
                {
                    "id": cid,
                    "qualified_name": _node_label(node),
                    "repo_path": repo_rel,
                    "root_path": root_path,
                    "layer": _layer_from_path(repo_rel),
                    "type": node.get("type", "unknown"),
                }
            )
        return out

    # --------------------------------------------------------------- context

    @staticmethod
    def _build_trace(chain: list[dict[str, Any]], failure: dict[str, Any]) -> list[str]:
        trace: list[str] = []
        if failure.get("route"):
            trace.append(f"{failure['route']} (route)")
        for c in chain:
            trace.append(f"{c['root_path']} :: {c['qualified_name']} ({c['layer']})")
        if not trace:
            trace.append("LynkMesh graph produced no call chain; see suspected_files.")
        return trace

    @staticmethod
    def _safe_patch_scope(
        chain: list[dict[str, Any]],
        failure: dict[str, Any],
        allowed_prefixes: tuple[str, ...],
    ) -> list[str]:
        """Files downstream of the failure: the call site + the intended definition.

        The failing symbol (e.g. ``TransactionModel::getMontlySummary``) is a typo and
        absent from the graph; the graph's chain end is the intended definition
        (``TransactionModel::getMonthlySummary``), and its predecessor is the call site.
        The route/controller entrypoint layer is excluded (no bug there), which also
        keeps edits inside the risk gate's <=3-file guardrail.
        """
        called_class = failure.get("called_class")
        target_idx: int | None = None
        if called_class:
            for idx in range(len(chain) - 1, -1, -1):
                qn = chain[idx]["qualified_name"]
                if qn == called_class or qn.startswith(called_class + "::"):
                    target_idx = idx
                    break

        scope: list[str] = []
        if target_idx is not None:
            if target_idx > 0:
                scope.append(chain[target_idx - 1]["root_path"])  # call site
            scope.append(chain[target_idx]["root_path"])  # intended definition
        else:
            # Fallback: all chain files except the entrypoint file.
            scope = [c["root_path"] for c in chain[1:]]

        if allowed_prefixes:
            scope = [p for p in scope if _in_scope(p, allowed_prefixes)]
        return _dedupe(scope)

    @staticmethod
    def _build_impact(chain: list[dict[str, Any]], failure: dict[str, Any]) -> list[str]:
        impact: list[str] = []
        if failure.get("route"):
            impact.append(failure["route"])
        if chain:
            entry = chain[0]
            impact.append(f"{entry['qualified_name']} HTTP entrypoint")
        # A short, human label from the deepest service/model method name.
        for c in chain[1:]:
            name = c["qualified_name"].split("::")[-1]
            feature = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).lower()
            impact.append(f"{feature} ({c['layer']})")
        if failure.get("symbol"):
            impact.append(f"{failure['symbol']} response contract")
        return _dedupe(impact) or ["unknown impact"]

    @staticmethod
    def _confidence(edges: list[dict[str, Any]]) -> float:
        confs = []
        for edge in edges:
            if edge.get("type") != "calls_confirmed":
                continue
            try:
                confs.append(float(edge.get("confidence") or 0))
            except (TypeError, ValueError):
                continue
        if not confs:
            return 0.5
        return round(min(confs), 2)

    @staticmethod
    def _build_notes(chain: list[dict[str, Any]], failure: dict[str, Any], confidence: float) -> str:
        if not chain:
            return "LynkMesh graph scan produced no calls_confirmed chain for this failure."
        chain_str = " -> ".join(c["qualified_name"] for c in chain)
        parts = [
            f"LynkMesh graph traced {chain_str} via calls_confirmed edges (confidence={confidence}).",
        ]
        if failure.get("symbol"):
            parts.append(
                f"Failure log reports {failure['symbol']} (type={failure['type']}); "
                "the graph defines the intended symbol at the chain end, indicating a call/definition mismatch."
            )
        parts.append("Safe patch scope is the call site plus the intended definition; the route/controller layer is out of scope.")
        return " ".join(parts)

    # --------------------------------------------------------------- evidence

    @staticmethod
    def _graph_evidence(
        chain: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        pack: dict[str, Any],
    ) -> dict[str, Any]:
        calls = [
            {
                "source": e.get("source_label") or e.get("source"),
                "target": e.get("target_label") or e.get("target"),
                "confidence": e.get("confidence"),
            }
            for e in edges
            if e.get("type") == "calls_confirmed"
        ]
        exec_ctx = pack.get("executive_context", {}) or {}
        return {
            "chain": [
                {
                    "qualified_name": c["qualified_name"],
                    "path": c["root_path"],
                    "layer": c["layer"],
                    "type": c["type"],
                }
                for c in chain
            ],
            "calls_confirmed": calls,
            "node_count": exec_ctx.get("node_count"),
            "edge_count": exec_ctx.get("edge_count"),
        }

    @staticmethod
    def _provenance(
        report: dict[str, Any] | None,
        pack: dict[str, Any],
        repo_path: Path,
        edges: list[dict[str, Any]],
    ) -> dict[str, Any]:
        report = report or {}
        rep_prov = report.get("provenance", {}) or {}
        identity = pack.get("project_identity", {}) or {}
        exec_ctx = pack.get("executive_context", {}) or {}
        guardrails = pack.get("guardrails", {}) or {}
        calls_count = sum(1 for e in edges if e.get("type") == "calls_confirmed")
        return {
            "source": "lynkmesh_real",
            "build_id": identity.get("build_id") or report.get("build", {}).get("build_id"),
            "content_hash": identity.get("content_hash")
            or report.get("build", {}).get("content_hash"),
            "graph_id": report.get("build", {}).get("graph_id"),
            "generator": rep_prov.get("generator", "lynkmesh"),
            "generator_version": rep_prov.get("generator_version"),
            "is_deterministic": bool(rep_prov.get("is_deterministic", guardrails.get("deterministic_facts_only"))),
            "profile": pack.get("profile"),
            "scan_path": str(repo_path),
            "graph_facts": {
                "node_count": exec_ctx.get("node_count"),
                "edge_count": exec_ctx.get("edge_count"),
                "node_type_breakdown": exec_ctx.get("node_type_breakdown", {}),
            },
            "calls_confirmed_count": calls_count,
        }
