import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from .helpers import SKIP_DIRS
from .inference import InferenceManager
from .treesitter_parser import parse_file, TREE_SITTER_AVAILABLE


class TreeNode:
    def __init__(self, value):
        self.value = value
        self.children = []
        self.is_file = False
        self.error_traces = []

    def add_child(self, child_node):
        self.children.append(child_node)


_DGAT_SCAN_TIMEOUT_SECONDS = int(os.getenv("DGAT_SCAN_TIMEOUT", "300"))


class DependencyAnalyzer:
    """Adapter around the `dgat` package (https://pypi.org/project/dgat/).

    Runs `dgat scan` on the project, loads the resulting dep_graph.json /
    file_tree.json / dgat_blueprint.md, and exposes the same public surface
    the rest of alpha-stack expects (`.graph`, `.dependency_details`,
    `.file_symbols`, `.get_dependencies`, `.get_dependents`,
    `.get_dependency_details`).
    """

    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()
        self.project_root: Optional[str] = None
        self.project_files: Set[str] = set()
        self.dependency_details: Dict[str, List[Dict[str, Optional[str]]]] = {}
        self.file_symbols: Dict[str, Dict[str, List[str]]] = {}
        self.folder_tree: Optional[TreeNode] = None
        self.blueprint: str = ""
        self.file_tree = None  # dgat FileTree (pydantic model) if loaded
        # Dirty-tracking: planner-edited files awaiting the next `dgat update`.
        self._dirty_files: Set[str] = set()
        # Cached lookups rebuilt on every state load.
        self._node_by_rel: Dict[str, Any] = {}
        self._edge_by_pair: Dict[tuple, Any] = {}
        # Active provider/model so run_update() can pass them straight through.
        self._dgat_provider: Optional[str] = None
        self._dgat_model: Optional[str] = None

    def set_folder_tree(self, folder_tree: TreeNode) -> None:
        self.folder_tree = folder_tree

    def analyze_project_files(
        self,
        project_root_path: str,
        folder_tree: TreeNode,
        folder_structure: str,
        on_status=None,
    ) -> None:
        from dgat.scanner import run_scan

        def _emit(msg):
            if on_status:
                on_status("progress", msg)

        self.set_folder_tree(folder_tree)
        self.project_root = os.path.abspath(project_root_path)

        # run_scan() calls the C++ binary, streams output, detects the
        # "scan complete. starting server" marker, kills the process at
        # that point (before the HTTP server starts), and returns — so the
        # 3 files (file_tree.json / dep_graph.json / dgat_blueprint.md)
        # are written without ever hanging on the backend server.
        _emit("Running dgat scan...")
        result = run_scan(project_root_path, provider=None, model=None, deps_only=False)
        if not result.success:
            raise RuntimeError(
                f"dgat scan failed for {self.project_root}: {result.message}"
            )
        _emit(f"dgat scan complete ({result.files_scanned} files, {result.edges} edges).")

        self._load_state_from_disk()

    def get_dependencies(self, file_path: str) -> List[str]:
        return [
            d["path"]
            for d in self.dependency_details.get(file_path, [])
            if d.get("kind") == "internal" and d.get("path")
        ]

    def get_dependents(self, file_path: str) -> List[str]:
        if file_path in self.graph:
            return list(self.graph.predecessors(file_path))
        return []

    def get_dependency_details(self, file_path: str) -> List[Dict[str, Optional[str]]]:
        return self.dependency_details.get(file_path, [])

    def _load_dep_graph(self) -> Tuple[Any, Dict[str, Any]]:
        from dgat.types import DepGraph

        dep_path = os.path.join(self.project_root, "dep_graph.json")
        if not os.path.isfile(dep_path):
            raise RuntimeError(f"dgat did not produce dep_graph.json at {dep_path}")
        with open(dep_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return DepGraph(**raw), raw

    def _load_file_tree(self):
        from dgat.types import FileTree

        tree_path = os.path.join(self.project_root, "file_tree.json")
        if not os.path.isfile(tree_path):
            return None
        with open(tree_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        try:
            return FileTree(**raw)
        except Exception:
            return None

    def _read_text(self, path: str) -> str:
        if not os.path.isfile(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def _populate_from_depgraph(self, dep_graph, dep_raw: Dict[str, Any]) -> None:
        raw_edges = dep_raw.get("edges") or []
        import_stmt_by_pair = {
            (e.get("from"), e.get("to")): e.get("import_stmt", "")
            for e in raw_edges
            if isinstance(e, dict)
        }

        for node in dep_graph.nodes:
            abs_path = node.abs_path or os.path.normpath(
                os.path.join(self.project_root, node.rel_path)
            )
            abs_path = os.path.normpath(abs_path)
            self.graph.add_node(abs_path)
            if os.path.isfile(abs_path):
                self.project_files.add(abs_path)

        for edge in dep_graph.edges:
            from_abs = os.path.normpath(
                os.path.join(self.project_root, edge.from_node)
            )
            to_abs = os.path.normpath(os.path.join(self.project_root, edge.to_node))
            self.graph.add_edge(from_abs, to_abs)
            stmt = import_stmt_by_pair.get((edge.from_node, edge.to_node), "") or edge.from_node
            self.dependency_details.setdefault(from_abs, []).append(
                {
                    "raw": stmt,
                    "kind": "internal",
                    "path": to_abs,
                    "description": edge.description or "",
                }
            )

    def _supplement_with_treesitter(self) -> None:
        """dgat (v1.0.x) has two gaps we patch up here:
          1. External (unresolved) imports are dropped entirely — so a file
             whose first import is e.g. `import requests` ends up skipped
             from the dep graph *completely*. We re-walk the tree and emit
             both external entries and any internal edges dgat missed.
          2. Class/function symbols aren't exposed at all.
        """
        if not TREE_SITTER_AVAILABLE or not self.project_root:
            return

        skip_extensions = {".pyc", ".pyo", ".pyd", ".so", ".dylib", ".dll", ".exe", ".bin"}
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
            for fname in files:
                if fname.startswith("."):
                    continue
                if Path(fname).suffix.lower() in skip_extensions:
                    continue
                abs_file = os.path.normpath(os.path.join(root, fname))
                try:
                    pr = parse_file(abs_file)
                except Exception:
                    continue
                if pr is None:
                    continue

                self.project_files.add(abs_file)
                self.graph.add_node(abs_file)
                self.file_symbols[abs_file] = {
                    "classes": list(pr.classes or []),
                    "functions": list(pr.functions or []),
                }

                existing = self.dependency_details.get(abs_file, [])
                existing_internal_paths: Set[str] = {
                    d.get("path") for d in existing if d.get("kind") == "internal" and d.get("path")
                }
                existing_internal_raw = {
                    d.get("raw") for d in existing if d.get("kind") == "internal"
                }
                seen_external: Set[str] = {
                    d.get("raw") for d in existing if d.get("kind") == "external"
                }

                for imp in pr.imports or []:
                    module = (imp.module or imp.raw or "").strip()
                    if not module:
                        continue

                    resolved = self._resolve_internal_import(abs_file, module)
                    if resolved:
                        if resolved in existing_internal_paths:
                            continue
                        existing_internal_paths.add(resolved)
                        existing_internal_raw.add(module)
                        self.graph.add_edge(abs_file, resolved)
                        self.dependency_details.setdefault(abs_file, []).append(
                            {
                                "raw": module,
                                "kind": "internal",
                                "path": resolved,
                                "description": "",
                            }
                        )
                        continue

                    if module.startswith("."):
                        # Relative import we couldn't resolve to a real file —
                        # skip (don't mislabel it as external).
                        continue
                    if module in existing_internal_raw or module in seen_external:
                        continue
                    seen_external.add(module)
                    self.dependency_details.setdefault(abs_file, []).append(
                        {"raw": module, "kind": "external", "path": None}
                    )

    # ------------------------------------------------------------------
    # State loading + incremental update
    # ------------------------------------------------------------------
    def _load_state_from_disk(self) -> None:
        """Re-read dgat state files and rebuild graph/details/lookups.

        Idempotent: clears previous state first. Called after `dgat scan`
        and after each `dgat update`.
        """
        # Reset everything derived from dgat output (folder_tree is owned by
        # the caller and stays untouched).
        self.graph = nx.DiGraph()
        self.project_files = set()
        self.dependency_details = {}
        self.file_symbols = {}
        self._node_by_rel = {}
        self._edge_by_pair = {}

        dep_graph_obj, dep_raw = self._load_dep_graph()
        self.file_tree = self._load_file_tree()
        if self.project_root:
            self.blueprint = self._read_text(
                os.path.join(self.project_root, "dgat_blueprint.md")
            )

        self._populate_from_depgraph(dep_graph_obj, dep_raw)
        self._supplement_with_treesitter()
        self._build_lookup_caches(dep_graph_obj, dep_raw)

    def _build_lookup_caches(self, dep_graph_obj, dep_raw: Dict[str, Any]) -> None:
        """Index file_tree nodes by rel_path and edges by (from, to)."""
        if self.file_tree is not None:
            def _walk(node):
                rp = (getattr(node, "rel_path", "") or "").replace("\\", "/").lstrip("./")
                if rp and getattr(node, "is_file", False):
                    self._node_by_rel[rp] = node
                for child in getattr(node, "children", []) or []:
                    _walk(child)
            _walk(self.file_tree)

        for raw_edge in dep_raw.get("edges") or []:
            if not isinstance(raw_edge, dict):
                continue
            f = (raw_edge.get("from") or "").replace("\\", "/").lstrip("./")
            t = (raw_edge.get("to") or "").replace("\\", "/").lstrip("./")
            if f and t:
                self._edge_by_pair[(f, t)] = raw_edge

    def mark_dirty(self, rel_path: str) -> None:
        """Flag a file as edited; the next `run_update()` will re-describe it."""
        if not rel_path:
            return
        norm = rel_path.replace("\\", "/").lstrip("./")
        self._dirty_files.add(norm)

    def has_dirty(self) -> bool:
        return bool(self._dirty_files)

    def pop_dirty(self) -> Set[str]:
        """Return and clear the dirty set."""
        out = set(self._dirty_files)
        self._dirty_files.clear()
        return out

    def is_dirty(self, rel_path: str) -> bool:
        if not rel_path:
            return False
        return rel_path.replace("\\", "/").lstrip("./") in self._dirty_files

    def run_update(self) -> Dict[str, Any]:
        """Run `dgat update` and reload state.

        Synchronous. Returns:
          {"ok": bool, "elapsed": float, "changed": int, "message": str}
        Caller decides whether to surface failures to the planner; this
        never raises (DGAT going down should not break the pipeline).
        """
        import time

        if not self.project_root:
            return {"ok": False, "elapsed": 0.0, "changed": 0,
                    "message": "no project_root set"}

        # Need a prior state to update from. If file_tree.json is missing,
        # dgat update silently no-ops — fall back to a full scan.
        tree_path = os.path.join(self.project_root, "file_tree.json")
        if not os.path.isfile(tree_path):
            return {"ok": False, "elapsed": 0.0, "changed": 0,
                    "message": "no prior dgat state; skipping update"}

        t0 = time.time()
        try:
            from dgat.scanner import run_update as _dgat_run_update
        except ImportError as exc:
            return {"ok": False, "elapsed": 0.0, "changed": 0,
                    "message": f"dgat package not installed: {exc}"}

        try:
            result = _dgat_run_update(self.project_root)
        except Exception as exc:
            return {"ok": False, "elapsed": time.time() - t0, "changed": 0,
                    "message": f"dgat update raised: {exc}"}

        elapsed = time.time() - t0
        if not getattr(result, "success", False):
            return {"ok": False, "elapsed": elapsed, "changed": 0,
                    "message": getattr(result, "message", "update failed")}

        # Reload state so callers see fresh descriptions/edges.
        try:
            self._load_state_from_disk()
        except Exception as exc:
            return {"ok": False, "elapsed": elapsed, "changed": 0,
                    "message": f"state reload failed: {exc}"}

        return {"ok": True, "elapsed": elapsed,
                "changed": -1,  # we don't parse stdout; -1 = unknown
                "message": "ok"}

    # ------------------------------------------------------------------
    # On-demand context lookups (used by ToolHandler)
    # ------------------------------------------------------------------
    def _normalize_rel(self, rel_path: str) -> str:
        return (rel_path or "").replace("\\", "/").lstrip("./")

    def find_node(self, rel_path: str):
        return self._node_by_rel.get(self._normalize_rel(rel_path))

    def get_file_context(self, rel_path: str, *, edge_desc_chars: int = 160) -> Dict[str, Any]:
        """Compact context block for auto-attaching to file reads.

        Shape:
          {
            "description": str,
            "depends_on":  [{"path": str, "edge": str, "import_stmt": str}],
            "depended_by": [{"path": str, "edge": str}],
          }
        Returns {} when DGAT has no record of the file (e.g. just-created).
        """
        node = self.find_node(rel_path)
        if node is None:
            return {}
        rp = self._normalize_rel(rel_path)
        out: Dict[str, Any] = {
            "description": (getattr(node, "description", "") or "")[:600],
        }

        deps = []
        for dep_rel in (getattr(node, "depends_on", []) or []):
            edge = self._edge_by_pair.get((rp, dep_rel)) or {}
            deps.append({
                "path": dep_rel,
                "edge": (edge.get("description") or "")[:edge_desc_chars],
                "import_stmt": (edge.get("import_stmt") or "")[:120],
            })
        if deps:
            out["depends_on"] = deps

        dependents = []
        for src_rel in (getattr(node, "depended_by", []) or []):
            edge = self._edge_by_pair.get((src_rel, rp)) or {}
            dependents.append({
                "path": src_rel,
                "edge": (edge.get("description") or "")[:edge_desc_chars],
            })
        if dependents:
            out["depended_by"] = dependents

        return out

    def get_file_edges(self, rel_path: str) -> Dict[str, Any]:
        """Full edge records for both directions. Used by `get_file_edges` tool."""
        node = self.find_node(rel_path)
        if node is None:
            return {"outgoing": [], "incoming": []}
        rp = self._normalize_rel(rel_path)
        outgoing = []
        for dep_rel in (getattr(node, "depends_on", []) or []):
            edge = self._edge_by_pair.get((rp, dep_rel)) or {}
            outgoing.append({
                "to": dep_rel,
                "import_stmt": edge.get("import_stmt") or "",
                "description": edge.get("description") or "",
            })
        incoming = []
        for src_rel in (getattr(node, "depended_by", []) or []):
            edge = self._edge_by_pair.get((src_rel, rp)) or {}
            incoming.append({
                "from": src_rel,
                "import_stmt": edge.get("import_stmt") or "",
                "description": edge.get("description") or "",
            })
        return {"outgoing": outgoing, "incoming": incoming}

    def compute_blast_radius(self, edited_rel_paths: Set[str], *, max_callers: int = 8) -> str:
        """Render a planner-prompt blast-radius section for a set of edits.

        Returns "" if nothing useful to show (no DGAT data, or no callers).
        """
        if not edited_rel_paths or self.file_tree is None:
            return ""

        sections = []
        for rp in sorted(edited_rel_paths):
            node = self.find_node(rp)
            if node is None:
                sections.append(f"▸ {rp} (NEW — not yet in DGAT graph)")
                continue
            desc = (getattr(node, "description", "") or "").strip()
            callers = list(getattr(node, "depended_by", []) or [])[:max_callers]

            block = [f"▸ {rp}"]
            if desc:
                block.append(f"  description: {desc[:300]}")
            if callers:
                block.append(f"  callers ({len(callers)}):")
                for c in callers:
                    edge = self._edge_by_pair.get((c, rp)) or {}
                    edesc = (edge.get("description") or "").strip()
                    if edesc:
                        block.append(f"    • {c} — {edesc[:140]}")
                    else:
                        block.append(f"    • {c}")
            else:
                block.append("  callers: (none)")
            sections.append("\n".join(block))

        return "\n\n".join(sections)

    def _resolve_internal_import(
        self, source_file: str, module: str
    ) -> Optional[str]:
        """Try to map an `import X` / `from X import ...` to a project file.

        Supports relative imports (`.b`, `..sub.c`) resolved against
        `source_file`'s directory, and absolute imports (`pkg.mod`)
        resolved against `self.project_root`. Returns an absolute path
        that exists on disk, or None.
        """
        if not module or not self.project_root:
            return None

        ext_candidates = (".py",)

        def try_paths(base: str, parts: list[str]) -> Optional[str]:
            if not parts:
                return None
            for ext in ext_candidates:
                cand = os.path.normpath(os.path.join(base, *parts) + ext)
                if os.path.isfile(cand):
                    return cand
            # package __init__.py
            cand = os.path.normpath(os.path.join(base, *parts, "__init__.py"))
            if os.path.isfile(cand):
                return cand
            return None

        if module.startswith("."):
            dots = 0
            while dots < len(module) and module[dots] == ".":
                dots += 1
            rel = module[dots:]
            base = os.path.dirname(source_file)
            for _ in range(max(0, dots - 1)):
                base = os.path.dirname(base)
            parts = [p for p in rel.split(".") if p]
            return try_paths(base, parts)

        parts = module.split(".")
        return try_paths(self.project_root, parts)


def build_dependency_graph_tree(
    project_root: str, dependency_analyzer: "DependencyAnalyzer"
) -> str:
    skip_dirs = SKIP_DIRS
    lines: List[str] = []

    def _walk_tree(dir_path: str, prefix: str = "", is_last: bool = True):
        rel_dir = os.path.relpath(dir_path, project_root)
        dir_name = (
            os.path.basename(dir_path) if rel_dir != "." else os.path.basename(project_root)
        )

        if dir_name.startswith(".") and dir_name != ".":
            return

        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{dir_name}/")

        child_prefix = prefix + ("    " if is_last else "│   ")

        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return

        dirs = [
            e
            for e in entries
            if os.path.isdir(os.path.join(dir_path, e))
            and not e.startswith(".")
            and e not in skip_dirs
        ]
        files = [
            e
            for e in entries
            if os.path.isfile(os.path.join(dir_path, e)) and not e.startswith(".")
        ]

        all_entries = dirs + files

        for i, entry in enumerate(all_entries):
            entry_path = os.path.join(dir_path, entry)
            entry_is_last = i == len(all_entries) - 1

            if os.path.isdir(entry_path):
                _walk_tree(entry_path, child_prefix, entry_is_last)
            else:
                file_connector = "└── " if entry_is_last else "├── "
                lines.append(f"{child_prefix}{file_connector}{entry}")

                abs_file = os.path.abspath(entry_path)
                dep_details = dependency_analyzer.dependency_details.get(abs_file, [])
                internal_deps = [
                    os.path.relpath(d["path"], project_root)
                    for d in dep_details
                    if d.get("kind") == "internal" and d.get("path")
                ]

                dependents_abs = dependency_analyzer.get_dependents(abs_file)
                dependents_rel = [
                    os.path.relpath(p, project_root) for p in dependents_abs
                ]

                file_syms = dependency_analyzer.file_symbols.get(abs_file, {})
                file_classes = file_syms.get("classes", [])
                file_functions = file_syms.get("functions", [])

                annot_prefix = child_prefix + ("    " if entry_is_last else "│   ")
                if file_classes:
                    lines.append(f"{annot_prefix}  classes: {', '.join(file_classes)}")
                if file_functions:
                    lines.append(f"{annot_prefix}  functions: {', '.join(file_functions)}")
                external_deps = sorted(
                    {
                        d["raw"]
                        for d in dep_details
                        if d.get("kind") == "external" and d.get("raw")
                    }
                )
                if internal_deps:
                    lines.append(f"{annot_prefix}  deps: {', '.join(internal_deps)}")
                if external_deps:
                    lines.append(f"{annot_prefix}  external: {', '.join(external_deps)}")
                if dependents_rel:
                    lines.append(f"{annot_prefix}  used-by: {', '.join(dependents_rel)}")

    try:
        _walk_tree(project_root)
    except Exception:
        pass

    return "\n".join(lines)
