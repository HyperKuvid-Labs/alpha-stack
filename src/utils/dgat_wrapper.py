import os
from typing import List, Optional, Dict, Any
from pathlib import Path

try:
    from dgat import run_scan, run_update, FileTree, DepGraph

    DGAT_AVAILABLE = True
except ImportError:
    DGAT_AVAILABLE = False


class DGATManager:
    def __init__(
        self, provider_config: dict, project_root: str, provider_name: str = None
    ):
        self.project_root = project_root
        self.provider_name = provider_name or provider_config.get(
            "active_provider", "openrouter"
        )
        self.provider_config = provider_config

        self.provider_map = {
            "google": "openai",
            "openai": "openai",
            "vllm": "vllm",
            "openrouter": "openrouter",
            "ollama": "ollama",
            "anthropic": "anthropic",
            "prime_intellect": "openrouter",
        }

        self._dgat_dir = os.path.join(project_root, ".dgat")

    def _get_dgat_provider_config(self) -> Dict[str, Any]:
        provider_key = self.provider_map.get(self.provider_name, "openrouter")

        if provider_key == "vllm":
            return {
                "provider": "vllm",
                "endpoint": "http://localhost:8000",
                "model": "Qwen/Qwen3.5-2B",
            }
        elif provider_key == "ollama":
            return {
                "provider": "ollama",
                "endpoint": "http://localhost:11434",
                "model": "llama3.2",
            }
        elif provider_key == "anthropic":
            return {
                "provider": "anthropic",
                "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
            }
        else:
            return {
                "provider": "openrouter",
                "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
            }

    def scan(self) -> bool:
        if not DGAT_AVAILABLE:
            print("[dgat] DGAT not available, skipping scan")
            return False

        if not os.path.exists(self.project_root):
            print(f"[dgat] Project root does not exist: {self.project_root}")
            return False

        try:
            config = self._get_dgat_provider_config()
            print(
                f"[dgat] Running scan on {self.project_root} with provider {config.get('provider')}"
            )

            run_scan(
                path=self.project_root,
                provider=config.get("provider", "openrouter"),
                endpoint=config.get("endpoint"),
                model=config.get("model"),
                api_key=config.get("api_key"),
            )
            print("[dgat] Scan completed successfully")
            return True
        except Exception as e:
            print(f"[dgat] Scan failed: {e}")
            return False

    def update(self) -> bool:
        if not DGAT_AVAILABLE:
            print("[dgat] DGAT not available, skipping update")
            return False

        if not os.path.exists(self.project_root):
            return False

        try:
            config = self._get_dgat_provider_config()
            print(f"[dgat] Running incremental update on {self.project_root}")

            run_update(
                path=self.project_root,
                provider=config.get("provider", "openrouter"),
                endpoint=config.get("endpoint"),
                model=config.get("model"),
                api_key=config.get("api_key"),
            )
            print("[dgat] Update completed successfully")
            return True
        except Exception as e:
            print(f"[dgat] Update failed: {e}")
            return False

    def get_file_description(self, rel_path: str) -> str:
        if not DGAT_AVAILABLE:
            return ""

        tree_path = os.path.join(self._dgat_dir, "file_tree.json")
        if not os.path.exists(tree_path):
            return ""

        try:
            tree = FileTree.load(tree_path)
            node = tree.find(rel_path)
            return node.description if node else ""
        except Exception as e:
            print(f"[dgat] Failed to get file description: {e}")
            return ""

    def get_dependencies(self, rel_path: str) -> List[str]:
        if not DGAT_AVAILABLE:
            return []

        graph_path = os.path.join(self._dgat_dir, "dep_graph.json")
        if not os.path.exists(graph_path):
            return []

        try:
            graph = DepGraph.load(graph_path)
            node = graph.get_node(rel_path)
            return node.depends_on if node else []
        except Exception as e:
            print(f"[dgat] Failed to get dependencies: {e}")
            return []

    def get_dependents(self, rel_path: str) -> List[str]:
        if not DGAT_AVAILABLE:
            return []

        graph_path = os.path.join(self._dgat_dir, "dep_graph.json")
        if not os.path.exists(graph_path):
            return []

        try:
            graph = DepGraph.load(graph_path)
            node = graph.get_node(rel_path)
            return node.depended_by if node else []
        except Exception as e:
            print(f"[dgat] Failed to get dependents: {e}")
            return []

    def get_blueprint(self) -> str:
        if not DGAT_AVAILABLE:
            return ""

        blueprint_path = os.path.join(self._dgat_dir, "dgat_blueprint.md")
        if not os.path.exists(blueprint_path):
            return ""

        try:
            with open(blueprint_path, "r") as f:
                return f.read()
        except Exception as e:
            print(f"[dgat] Failed to get blueprint: {e}")
            return ""

    def get_file_tree(self) -> str:
        if not DGAT_AVAILABLE:
            return ""

        tree_path = os.path.join(self._dgat_dir, "file_tree.json")
        if not os.path.exists(tree_path):
            return ""

        try:
            tree = FileTree.load(tree_path)
            return tree.to_tree_string()
        except Exception as e:
            print(f"[dgat] Failed to get file tree: {e}")
            return ""

    def get_dep_graph(self) -> Dict[str, Any]:
        if not DGAT_AVAILABLE:
            return {"nodes": [], "edges": []}

        graph_path = os.path.join(self._dgat_dir, "dep_graph.json")
        if not os.path.exists(graph_path):
            return {"nodes": [], "edges": []}

        try:
            graph = DepGraph.load(graph_path)
            return {
                "nodes": [
                    {
                        "id": node.id,
                        "rel_path": node.rel_path,
                        "description": node.description,
                        "depends_on": node.depends_on,
                        "depended_by": node.depended_by,
                    }
                    for node in graph.nodes
                ],
                "edges": [
                    {
                        "from": edge.from_path,
                        "to": edge.to_path,
                        "import_stmt": edge.import_stmt,
                        "description": edge.description,
                    }
                    for edge in graph.edges
                ],
            }
        except Exception as e:
            print(f"[dgat] Failed to get dep graph: {e}")
            return {"nodes": [], "edges": []}

    def search_files(self, query: str) -> List[Dict[str, str]]:
        if not DGAT_AVAILABLE:
            return []

        tree_path = os.path.join(self._dgat_dir, "file_tree.json")
        if not os.path.exists(tree_path):
            return []

        try:
            tree = FileTree.load(tree_path)
            results = tree.search(query)
            return [
                {"rel_path": r.rel_path, "description": r.description} for r in results
            ]
        except Exception as e:
            print(f"[dgat] Failed to search files: {e}")
            return []


def build_project_structure_tree(project_root: str) -> str:
    import os
    from ..utils.helpers import SKIP_DIRS

    skip_dirs = SKIP_DIRS
    lines = []

    def _walk_tree(dir_path: str, prefix: str = "", is_last: bool = True):
        rel_dir = os.path.relpath(dir_path, project_root)
        dir_name = (
            os.path.basename(dir_path)
            if rel_dir != "."
            else os.path.basename(project_root)
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

    try:
        _walk_tree(project_root)
    except Exception:
        pass

    return "\n".join(lines)
