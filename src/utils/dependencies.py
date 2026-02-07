import os
import json
import re
from typing import Dict, List, Optional, Set
from pathlib import Path
import networkx as nx
from jinja2 import Environment, FileSystemLoader
from .helpers import get_client, retry_api_call, SKIP_DIRS, MODEL_NAME, GENERATABLE_FILES, GENERATABLE_FILENAMES


class TreeNode:
    def __init__(self, value):
        self.value = value
        self.children = []
        self.is_file = False
        self.error_traces = []

    def add_child(self, child_node):
        self.children.append(child_node)

class DependencyError:
    def __init__(self, file_path: str, error_type: str, message: str,
                 dependency: Optional[str] = None, affected_files: Optional[List[str]] = None,
                 coupling_details: Optional[Dict] = None):
        self.file_path = file_path
        self.error_type = error_type
        self.message = message
        self.dependency = dependency
        self.affected_files = affected_files or []
        self.coupling_details = coupling_details or {}

    def to_dict(self, project_root: Optional[str] = None):
        if project_root and self.file_path:
            file_rel = os.path.relpath(self.file_path, project_root)
        else:
            file_rel = self.file_path or ""

        affected_files_rel = []
        for f in self.affected_files:
            if project_root and f:
                affected_files_rel.append(os.path.relpath(f, project_root))
            else:
                affected_files_rel.append(f or "")

        result = {
            "file": file_rel,
            "error": self.message,
            "error_type": self.error_type,
            "dependency": self.dependency,
            "affected_files": affected_files_rel,
            "line_number": None
        }

        if self.coupling_details:
            result["coupling_details"] = self.coupling_details

        return result


class DependencyAnalyzer:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.supported_extensions = {
            '.py': 'python', '.pyi': 'python',
            '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
            '.mjs': 'javascript', '.cjs': 'javascript',
            '.java': 'java', '.kt': 'jvm', '.kts': 'jvm', '.scala': 'jvm', '.groovy': 'jvm',
            '.php': 'php', '.phtml': 'php',
            '.rs': 'rust', '.go': 'go',
            '.c': 'c', '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp',
            '.h': 'c-header', '.hpp': 'cpp-header',
            '.cs': 'csharp', '.m': 'objective-c', '.mm': 'objective-c', '.swift': 'swift',
            '.rb': 'ruby', '.ex': 'elixir', '.exs': 'elixir', '.erl': 'erlang',
            '.html': 'html', '.htm': 'html', '.xhtml': 'html',
            '.css': 'css', '.scss': 'scss', '.sass': 'sass', '.less': 'less',
            '.json': 'json', '.yml': 'yaml', '.yaml': 'yaml',
            '.sql': 'sql', '.sol': 'solidity',
            '.vue': 'vue', '.svelte': 'svelte', '.dart': 'dart',
        }
        self.project_root: Optional[str] = None
        self.project_files: Set[str] = set()
        self.dependency_details: Dict[str, List[Dict[str, Optional[str]]]] = {}
        self.folder_tree: Optional[TreeNode] = None
        template_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'prompts')
        if os.path.exists(template_dir):
            self.jinja_env = Environment(
                loader=FileSystemLoader(template_dir),
                trim_blocks=True,
                lstrip_blocks=True
            )
        else:
            self.jinja_env = None

    def set_folder_tree(self, folder_tree: TreeNode) -> None:
        self.folder_tree = folder_tree

    def analyze_project_files(self, project_root_path: str, folder_tree: TreeNode, folder_structure: str) -> None:
        self.set_folder_tree(folder_tree)

        skip_extensions = {'.pyc', '.pyo', '.pyd', '.so', '.dylib', '.dll', '.exe', '.bin'}

        for root, dirs, files in os.walk(project_root_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for file in files:
                if file.startswith('.'):
                    continue
                file_ext = Path(file).suffix.lower()
                if file_ext in skip_extensions:
                    continue

                file_path = os.path.join(root, file)

                if not os.path.isfile(file_path):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self.add_file(file_path, content, folder_structure)
                except Exception:
                    pass

    def add_file(self, file_path: str, content: str, folder_structure: str):
        abs_path = os.path.abspath(file_path)
        self.project_files.add(abs_path)
        self._update_project_root()

        self.graph.add_node(abs_path)
        outgoing = list(self.graph.out_edges(abs_path))
        if outgoing:
            self.graph.remove_edges_from(outgoing)

        file_ext = Path(abs_path).suffix.lower()
        language = self.supported_extensions.get(file_ext, 'unknown')
        dependencies = self.extract_dependencies(abs_path, content, folder_structure, language)

        details: List[Dict[str, Optional[str]]] = []

        for dep in sorted(dependencies):
            info = self._classify_dependency(abs_path, dep, language)
            details.append(info)
            target_path = info.get("path")
            if info.get("kind") == "internal" and target_path:
                normalized_target = os.path.abspath(target_path)
                self.graph.add_node(normalized_target)
                if not self.graph.has_edge(abs_path, normalized_target):
                    self.graph.add_edge(abs_path, normalized_target)

        self.dependency_details[abs_path] = details

    def extract_dependencies(self, file_path: str, content: str, folder_structure: str, language: Optional[str] = None) -> Set[str]:
        dependencies = set()
        file_dir = os.path.dirname(file_path)
        file_ext = Path(file_path).suffix.lower()

        language = language or self.supported_extensions.get(file_ext, 'unknown')
        if language == 'python':
            dependencies.update(self._extract_python_dependencies(file_path, content, file_dir))
        elif language in ['javascript', 'typescript']:
            dependencies.update(self._extract_js_ts_dependencies(file_path, content, file_dir))
        elif language == 'java':
            dependencies.update(self._extract_java_dependencies(content))
        elif language == 'go':
            dependencies.update(self._extract_go_dependencies(content))
        elif language == 'rust':
            dependencies.update(self._extract_rust_dependencies(content))

        return dependencies

    def _update_project_root(self) -> None:
        if not self.project_files:
            return
        try:
            self.project_root = os.path.commonpath(list(self.project_files))
        except ValueError:
            pass

    def _classify_dependency(self, source_path: str, raw_dep: str, language: str) -> Dict[str, Optional[str]]:
        raw_dep = raw_dep.strip()
        if not raw_dep:
            return {"raw": raw_dep, "kind": "external"}

        resolved_path = self._resolve_relative_path(source_path, raw_dep)
        filename = self._extract_filename_from_dependency(raw_dep)

        if resolved_path and os.path.isfile(resolved_path):
            return {
                "raw": raw_dep,
                "kind": "internal",
                "path": os.path.abspath(resolved_path)
            }

        if filename:
            matching_files = self._find_all_files_by_name(filename, language)
            if matching_files:
                best_match = self._find_best_match_path(raw_dep, matching_files)
                if best_match:
                    return {
                        "raw": raw_dep,
                        "kind": "internal",
                        "path": os.path.abspath(best_match)
                    }

        return {"raw": raw_dep, "kind": "external"}

    def _extract_filename_from_dependency(self, raw_dep: str) -> str:
        if not raw_dep:
            return ""

        dep = raw_dep.strip()
        if dep.startswith('./'):
            dep = dep[2:]
        elif dep.startswith('../'):
            dep = os.path.basename(dep)
        elif dep.startswith('.'):
            dep = dep.lstrip('.')

        dep = dep.lstrip('/')

        if '::' in dep:
            parts = dep.split('::')
            filename = parts[-1]
        elif '/' in dep or '\\' in dep:
            filename = os.path.basename(dep)
        elif '.' in dep:
            parts = dep.split('.')
            common_extensions = {'h', 'hpp', 'cpp', 'c', 'cc', 'cxx', 'py', 'js', 'ts',
                               'jsx', 'tsx', 'java', 'go', 'rs', 'rb', 'php', 'cs',
                               'swift', 'kt', 'scala', 'm', 'mm', 'html', 'css', 'scss'}

            if len(parts) == 2 and parts[-1].lower() in common_extensions:
                filename = parts[0]
            elif len(parts) > 2:
                filename = parts[-1]
            else:
                if len(parts[-1]) <= 5:
                    filename = parts[0]
                else:
                    filename = parts[-1]
        else:
            filename = dep

        filename = os.path.splitext(filename)[0] if os.path.splitext(filename)[1] else filename

        return filename

    def _resolve_relative_path(self, source_path: str, raw_dep: str) -> Optional[str]:
        if not raw_dep:
            return None

        raw_dep = raw_dep.strip()

        if raw_dep.startswith('.') or raw_dep.startswith('./'):
            base_dir = os.path.dirname(source_path)

            if raw_dep.startswith('./'):
                rel_path = raw_dep[2:]
                target_path = os.path.join(base_dir, rel_path)
                return self._resolve_file_path(target_path, source_path)

            if raw_dep.startswith('.'):
                level = len(raw_dep) - len(raw_dep.lstrip('.'))
                remainder = raw_dep[level:]

                target_dir = base_dir
                for _ in range(max(level - 1, 0)):
                    target_dir = os.path.dirname(target_dir)

                if remainder:
                    rel_path = remainder.replace('.', os.sep).replace('/', os.sep)
                    target_path = os.path.join(target_dir, rel_path)
                else:
                    target_path = target_dir

                return self._resolve_file_path(target_path, source_path)

        if raw_dep.startswith('/'):
            if self.project_root:
                rel_path = raw_dep[1:]
                target_path = os.path.join(self.project_root, rel_path)
                return self._resolve_file_path(target_path, source_path)

        if '.' in raw_dep and not raw_dep.startswith('.') and not raw_dep.startswith('/'):
            if self.project_root:
                parts = raw_dep.split('.')
                possible_bases = ['src', 'lib', 'app', '']
                for base in possible_bases:
                    if base:
                        package_path = os.path.join(self.project_root, base, *parts)
                    else:
                        package_path = os.path.join(self.project_root, *parts)

                    py_file = package_path + '.py'
                    if os.path.isfile(py_file):
                        return os.path.abspath(py_file)

                    if os.path.isdir(package_path):
                        init_file = os.path.join(package_path, '__init__.py')
                        if os.path.isfile(init_file):
                            return os.path.abspath(init_file)

        return None

    def _resolve_file_path(self, base_path: str, source_path: str) -> Optional[str]:
        source_ext = Path(source_path).suffix.lower()

        base_path = os.path.normpath(base_path)

        if os.path.isfile(base_path):
            return os.path.abspath(base_path)

        possible_extensions = self._get_possible_extensions(source_ext)

        if source_ext:
            candidate = base_path + source_ext
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        for ext in possible_extensions:
            candidate = base_path + ext
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        if os.path.isdir(base_path):
            for ext in possible_extensions:
                index_file = os.path.join(base_path, 'index' + ext)
                if os.path.isfile(index_file):
                    return os.path.abspath(index_file)
                if ext == '.py':
                    init_file = os.path.join(base_path, '__init__.py')
                    if os.path.isfile(init_file):
                        return os.path.abspath(init_file)

        return None

    def _get_possible_extensions(self, source_ext: str) -> List[str]:
        extension_map = {
            '.py': ['.py'],
            '.js': ['.js', '.jsx', '.mjs', '.cjs', '.json'],
            '.jsx': ['.js', '.jsx', '.mjs', '.cjs'],
            '.ts': ['.ts', '.tsx', '.d.ts'],
            '.tsx': ['.ts', '.tsx', '.d.ts'],
            '.java': ['.java'],
            '.kt': ['.kt', '.kts'],
            '.rs': ['.rs'],
            '.go': ['.go'],
            '.rb': ['.rb'],
            '.php': ['.php', '.phtml'],
            '.cs': ['.cs'],
            '.swift': ['.swift'],
            '.cpp': ['.cpp', '.c', '.hpp', '.h'],
            '.c': ['.c', '.h'],
        }

        return extension_map.get(source_ext, [source_ext] if source_ext else [])

    def _extract_python_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()

        imports = re.findall(r'^\s*import\s+([a-zA-Z_][\w\., \t]*)', content, re.MULTILINE)
        for imp in imports:
            for part in imp.split(','):
                module = part.strip().split()[0] if part.strip() else ''
                if module and not module.startswith('#'):
                    dependencies.add(module)

        from_imports = re.findall(r'^\s*from\s+([a-zA-Z_][\w\.]*)\s+import', content, re.MULTILINE)
        dependencies.update(from_imports)

        relative_imports_with_path = re.findall(r'^\s*from\s+(\.+[a-zA-Z_][\w\.]*)\s+import', content, re.MULTILINE)
        dependencies.update(relative_imports_with_path)

        bare_relative_imports = re.findall(r'^\s*from\s+(\.+)\s+import\s+([a-zA-Z_][\w\., \t]*)', content, re.MULTILINE)
        for dots, modules in bare_relative_imports:
            num_dots = len(dots)
            for module in modules.split(','):
                module = module.strip().split()[0] if module.strip() else ''
                if module and not module.startswith('#'):
                    if num_dots == 1:
                        relative_path = f"./{module}"
                    else:
                        parent_dirs = "../" * (num_dots - 1)
                        relative_path = f"{parent_dirs}{module}"
                    dependencies.add(relative_path)

        return dependencies

    def _extract_js_ts_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()

        es6_imports = re.findall(r'import\s+(?:[\w{}\*\s,]+?\s+from\s+)?[\'"]([^\'"]+)[\'"]', content)
        dependencies.update(es6_imports)

        requires = re.findall(r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content)
        dependencies.update(requires)

        dynamic_imports = re.findall(r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content)
        dependencies.update(dynamic_imports)

        return dependencies

    def _extract_java_dependencies(self, content: str) -> Set[str]:
        dependencies = set()
        imports = re.findall(r'^\s*import\s+(?:static\s+)?([a-zA-Z0-9_.*]+);', content, flags=re.MULTILINE)
        dependencies.update(imports)
        return dependencies

    def _extract_go_dependencies(self, content: str) -> Set[str]:
        dependencies = set()
        imports = re.findall(r'import\s+(?:[a-zA-Z0-9_]+\s+)?["]([^"]+)["]', content)
        dependencies.update(imports)

        block_imports = re.findall(r'import\s*\((.*?)\)', content, flags=re.DOTALL)
        for block in block_imports:
            matches = re.findall(r'"([^"]+)"', block)
            dependencies.update(matches)

        return dependencies

    def _extract_rust_dependencies(self, content: str) -> Set[str]:
        dependencies = set()

        externs = re.findall(r'extern\s+crate\s+([a-zA-Z0-9_]+)', content)
        dependencies.update(externs)

        uses = re.findall(r'\b(?:pub\s+)?use\s+([a-zA-Z0-9_:{}*,\s]+);', content)
        dependencies.update([u.strip() for u in uses])

        mods = re.findall(r'\b(?:pub\s+)?mod\s+([a-zA-Z0-9_]+)\s*;', content)
        dependencies.update(mods)

        return dependencies

    def get_dependencies(self, file_path: str) -> List[str]:
        abs_path = os.path.abspath(file_path)
        details = self.dependency_details.get(abs_path, [])
        internal_paths = [item.get('path') for item in details if item.get('kind') == 'internal' and item.get('path')]
        return [os.path.abspath(path) for path in internal_paths if path]

    def get_dependency_details(self, file_path: str) -> List[Dict[str, Optional[str]]]:
        abs_path = os.path.abspath(file_path)
        return self.dependency_details.get(abs_path, [])

    def get_dependents(self, file_path: str) -> List[str]:
        abs_path = os.path.abspath(file_path)
        return list(self.graph.predecessors(abs_path))

    def _find_all_files_by_name(self, filename: str, language: str) -> List[str]:
        matching_files = []
        filename_basename = os.path.splitext(filename)[0]

        possible_extensions = []
        for ext, lang in self.supported_extensions.items():
            if lang == language:
                possible_extensions.append(ext)

        for file_path in self.project_files:
            file_basename = os.path.splitext(os.path.basename(file_path))[0]
            file_ext = Path(file_path).suffix.lower()

            if file_basename == filename_basename:
                if file_ext in possible_extensions or not possible_extensions:
                    matching_files.append(file_path)

        return matching_files

    def _find_best_match_path(self, dependency_path: str, candidate_paths: List[str]) -> Optional[str]:
        if not candidate_paths:
            return None

        if len(candidate_paths) == 1:
            return candidate_paths[0]

        dep_normalized = dependency_path.replace('\\', '/').lower().strip('/')
        dep_parts = [p for p in dep_normalized.split('/') if p]

        best_match = None
        best_score = -1

        for candidate in candidate_paths:
            if self.project_root:
                rel_candidate = os.path.relpath(candidate, self.project_root)
            else:
                rel_candidate = candidate

            candidate_normalized = rel_candidate.replace('\\', '/').lower().strip('/')
            candidate_parts = [p for p in candidate_normalized.split(os.sep) if p]

            score = 0
            for i, dep_part in enumerate(dep_parts):
                if i < len(candidate_parts) and dep_part == candidate_parts[i]:
                    score += 1
                elif dep_part in candidate_parts:
                    score += 0.5

            if score > best_score or (score == best_score and len(candidate_parts) < len(best_match.split(os.sep) if best_match else [])):
                best_score = score
                best_match = candidate

        return best_match


class DependencyFeedbackLoop:
    def __init__(self, dependency_analyzer: DependencyAnalyzer, project_root: str,
                 software_blueprint: Optional[Dict] = None,
                 folder_structure: Optional[str] = None,
                 file_output_format: Optional[Dict] = None,
                 pm=None, error_tracker=None):
        from .tools import ToolHandler
        from ..agents.planner import PlanningAgent
        from ..agents.corrector import ExecutorAgent
        from .prompt_manager import PromptManager
        from .error_tracker import ErrorTracker

        self.dependency_analyzer = dependency_analyzer
        self.project_root = project_root
        self.software_blueprint = software_blueprint or {}
        self.folder_structure = folder_structure or ""
        self.file_output_format = file_output_format or {}
        self.pm = pm or PromptManager(templates_dir="prompts")
        self.max_iterations = 25
        folder_tree = getattr(self.dependency_analyzer, "folder_tree", None)
        self.error_tracker = error_tracker or ErrorTracker(project_root, folder_tree)
        self.tool_handler = ToolHandler(project_root, self.error_tracker, dependency_analyzer=self.dependency_analyzer)

        self.planning_agent = PlanningAgent(
            project_root=project_root,
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            file_output_format=self.file_output_format,
            pm=self.pm,
            error_tracker=self.error_tracker,
            tool_handler=self.tool_handler
        )

        self.executor_agent = ExecutorAgent(
            project_root=project_root,
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            file_output_format=self.file_output_format,
            pm=self.pm,
            error_tracker=self.error_tracker,
            tool_handler=self.tool_handler
        )

    def walk_project_files(self) -> List[str]:
        files = []

        for root, dirs, filenames in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]

            for filename in filenames:
                if filename.startswith('.') and filename not in GENERATABLE_FILENAMES:
                    continue

                file_ext = Path(filename).suffix.lower()

                if filename not in GENERATABLE_FILENAMES and file_ext not in GENERATABLE_FILES:
                    continue

                file_path = os.path.join(root, filename)
                if os.path.isfile(file_path):
                    files.append(os.path.abspath(file_path))

        return sorted(files)

    def check_file_dependencies(self, file_path: str, fix_immediately: bool = False) -> List[DependencyError]:
        errors = []
        dep_details = self.dependency_analyzer.get_dependency_details(file_path)

        if not dep_details:
            return errors

        project_files = self.dependency_analyzer.project_files

        for dep_info in dep_details:
            if dep_info.get("kind") == "internal":
                dep_path = dep_info.get("path")
                raw_dep = dep_info.get("raw", "")

                if not dep_path:
                    errors.append(DependencyError(
                        file_path=file_path,
                        error_type="MISSING_PATH",
                        message=f"Dependency '{raw_dep}' resolved to None",
                        dependency=raw_dep
                    ))
                    continue

                abs_dep_path = os.path.abspath(dep_path)
                if abs_dep_path not in project_files:
                    errors.append(DependencyError(
                        file_path=file_path,
                        error_type="FILE_NOT_IN_PROJECT",
                        message=f"Dependency file '{os.path.relpath(dep_path, self.project_root)}' is not in the project files set",
                        dependency=raw_dep,
                        affected_files=[dep_path]
                    ))
                    continue

                if not os.path.exists(dep_path):
                    errors.append(DependencyError(
                        file_path=file_path,
                        error_type="FILE_NOT_FOUND",
                        message=f"Dependency file does not exist: {dep_path}",
                        dependency=raw_dep,
                        affected_files=[dep_path]
                    ))
                    continue

                coupling_error = self.check_coupling(file_path, dep_path, raw_dep)

                if coupling_error:
                    errors.append(coupling_error)

        return errors

    def check_coupling(self, source_file: str, target_file: str, dependency: str) -> Optional[DependencyError]:
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                source_content = f.read()

            with open(target_file, 'r', encoding='utf-8') as f:
                target_content = f.read()

            return self._agent_check_coupling(source_file, target_file, source_content, target_content, dependency)
        except Exception as e:
            return DependencyError(
                file_path=source_file,
                error_type="COUPLING_CHECK_ERROR",
                message=f"Error checking coupling: {str(e)}",
                dependency=dependency,
                affected_files=[target_file]
            )

    def _agent_check_coupling(self, source_file: str, target_file: str,
                              source_content: str, target_content: str,
                              dependency: str) -> Optional[DependencyError]:
        try:
            client = get_client()

            source_rel_path = os.path.relpath(source_file, self.project_root)
            target_rel_path = os.path.relpath(target_file, self.project_root)

            prompt = f"""Analyze code coupling between two files.

Source: {source_rel_path}
Target: {target_rel_path}
Import: {dependency}

Source:
```
{source_content[:2000]}
```

Target:
```
{target_content[:2000]}
```

Check:
1. Import path matches target file path
2. Imports/exports match
3. Symbols imported are exported
4. No signature mismatches
5. Types match

Respond JSON:
{{
    "has_error": true/false,
    "error_type": "PATH_MISMATCH"|"COUPLING_MISMATCH"|"MISSING_EXPORT"|"TYPE_MISMATCH"|"SIGNATURE_MISMATCH",
    "message": "description",
    "corrected_import": "fix if path mismatch",
    "missing_symbols": ["symbol1"],
    "type_mismatches": ["name: expected X, got Y"],
    "signature_mismatches": ["name: expected (params), got (params)"]
}}

Set has_error false if no issues."""

            response = retry_api_call(
                client.models.generate_content,
                model=MODEL_NAME,
                contents=prompt
            )

            text = response.text or ""
            json_match = re.search(r'\{.*?\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if result.get("has_error"):
                    coupling_details = {
                        "missing_symbols": result.get("missing_symbols", []),
                        "type_mismatches": result.get("type_mismatches", []),
                        "signature_mismatches": result.get("signature_mismatches", []),
                        "corrected_import": result.get("corrected_import")
                    }

                    return DependencyError(
                        file_path=source_file,
                        error_type=result.get("error_type", "COUPLING_MISMATCH"),
                        message=result.get("message", "Coupling mismatch detected"),
                        dependency=dependency,
                        affected_files=[target_file],
                        coupling_details=coupling_details
                    )
            return None
        except Exception:
            return None

    def _get_changed_files_from_tracker(self) -> Set[str]:
        changed_files = set()
        for change_entry in self.error_tracker.change_log:
            file_path = change_entry.get("file", "")
            if file_path:
                if not os.path.isabs(file_path):
                    abs_path = os.path.join(self.project_root, file_path)
                else:
                    abs_path = file_path
                changed_files.add(os.path.abspath(abs_path))
        return changed_files

    def _get_files_to_recheck(self, changed_files: Set[str]) -> Set[str]:
        files_to_check = set(changed_files)

        for changed_file in changed_files:
            try:
                dependents = self.dependency_analyzer.get_dependents(changed_file)
                files_to_check.update(dependents)
            except Exception:
                pass

        return files_to_check

    def _reanalyze_changed_files(self, changed_files: Set[str]) -> None:
        for file_path in changed_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.dependency_analyzer.add_file(file_path, content, self.folder_structure)
                except Exception:
                    pass

    def run_feedback_loop(self) -> Dict:
        all_files = self.walk_project_files()
        previous_errors = set()
        stuck_iterations = 0
        max_stuck_iterations = 20
        files_to_check = None

        for iteration in range(1, self.max_iterations + 1):
            print(f"[dep_resolution] iteration={iteration}")
            changes_before = len(self.error_tracker.change_log)

            if files_to_check is None:
                files_to_check = set(all_files)

            all_errors = []

            for file_path in files_to_check:
                errors = self.check_file_dependencies(file_path, fix_immediately=False)
                all_errors.extend(errors)

            if not all_errors:
                print("[dep_resolution] no errors found")
                return {
                    "success": True,
                    "iterations": iteration,
                    "remaining_errors": []
                }

            print(f"[dep_resolution] errors_found={len(all_errors)}")
            current_error_signatures = {
                (e.file_path, e.error_type, e.message[:100]) for e in all_errors
            }

            if current_error_signatures == previous_errors:
                stuck_iterations += 1

                if stuck_iterations >= max_stuck_iterations:
                    print("[dep_resolution] stuck errors detected, stopping")
                    return {
                        "success": False,
                        "iterations": iteration,
                        "remaining_errors": [e.to_dict(self.project_root) for e in all_errors],
                        "reason": "stuck_errors"
                    }
            else:
                stuck_iterations = 0
                previous_errors = current_error_signatures

            fixable_errors = list(all_errors)

            if not fixable_errors:
                print("[dep_resolution] no fixable errors")
                return {
                    "success": False,
                    "iterations": iteration,
                    "remaining_errors": [e.to_dict(self.project_root) for e in all_errors],
                    "reason": "unfixable_errors"
                }

            errors_dict = [e.to_dict(self.project_root) for e in fixable_errors]
            error_info = {
                "error_type": "dependency",
                "error": "Dependency resolution errors",
                "errors": errors_dict
            }
            is_repeat = self.error_tracker.is_repeat_error(error_info)
            if is_repeat:
                error_info["repeat"] = True
                print("[dep_resolution] repeat_error=true")
            error_id = self.error_tracker.log_error(error_info)

            tasks = self.planning_agent.plan_tasks(errors=errors_dict, error_type="dependency", error_ids=[error_id])
            if tasks:
                print(f"[dep_resolution] tasks_planned={len(tasks)}")
                changed_files = set()
                for task in tasks:
                    result = self.executor_agent.execute_task(task)
                    if result.get("changed_files"):
                        changed_files.update(result["changed_files"])
                    self.planning_agent.invalidate_cache()
                    self.executor_agent.invalidate_cache()

                if changed_files:
                    print(f"[dep_resolution] changed_files={len(changed_files)}")
                    self._reanalyze_changed_files(changed_files)
                    files_to_check = self._get_files_to_recheck(changed_files)
                    error_files = {os.path.abspath(e.file_path) for e in all_errors if e.file_path}
                    files_to_check.update(error_files)
                else:
                    print("[dep_resolution] no file changes applied")
                    files_to_check = set(all_files)
            else:
                print("[dep_resolution] no tasks returned from planner")
                files_to_check = set(all_files)

        print("[dep_resolution] max_iterations reached")
        return {
            "success": False,
            "iterations": self.max_iterations,
            "remaining_errors": [e.to_dict(self.project_root) for e in all_errors],
            "reason": "max_iterations"
        }

