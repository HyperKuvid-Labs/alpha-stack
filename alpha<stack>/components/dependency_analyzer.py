import networkx as nx
import ast 
import re
import os
import json
from typing import List, Set, Dict, Any, Optional
from pathlib import Path

class DependencyAnalyzer:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.go': 'go',
            '.rs': 'rust',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.dart': 'dart',
            '.r': 'r',
            '.m': 'objective-c',
            '.mm': 'objective-c',
            '.pl': 'perl',
            '.lua': 'lua',
            '.hs': 'haskell',
            '.clj': 'clojure',
            '.ex': 'elixir',
            '.erl': 'erlang',
            '.fs': 'fsharp',
            '.ml': 'ocaml',
            '.scm': 'scheme',
            '.rkt': 'racket',
            
            '.html': 'html',
            '.htm': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.less': 'less',
            '.vue': 'vue',
            '.svelte': 'svelte',
            
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            
            '.sql': 'sql',
            '.mysql': 'sql',
            '.pgsql': 'sql',
            '.sqlite': 'sql',
            
            '.sol': 'solidity',
            '.vy': 'vyper',
            '.cairo': 'cairo',
            '.move': 'move',
            '.clar': 'clarity',
            
            '.dockerfile': 'dockerfile',
            '.tf': 'terraform',
            '.hcl': 'terraform',
            '.sh': 'shell',
            '.bash': 'shell',
            '.zsh': 'shell',
            '.fish': 'shell',
            '.ps1': 'powershell',
            '.bat': 'batch',
            '.cmd': 'batch',
            
            '.gradle': 'gradle',
            '.maven': 'maven',
            '.cmake': 'cmake',
            '.make': 'makefile',
            '.mk': 'makefile'
        }

    def add_file(self, file_path: str, content: str):
        self.graph.add_node(file_path)
        dependencies = self.extract_dependencies(file_path, content)
        for dep in dependencies:
            self.graph.add_edge(file_path, dep)
    
    def extract_dependencies(self, file_path: str, content: str) -> Set[str]:
        dependencies = set()
        file_dir = os.path.dirname(file_path)
        file_ext = Path(file_path).suffix.lower()
        
        language = self.supported_extensions.get(file_ext, 'unknown')
        
        if language == 'python':
            dependencies.update(self._extract_python_dependencies(file_path, content, file_dir))
        elif language in ['javascript', 'typescript']:
            dependencies.update(self._extract_js_ts_dependencies(file_path, content, file_dir))
        elif language == 'java':
            dependencies.update(self._extract_java_dependencies(file_path, content, file_dir))
        elif language == 'go':
            dependencies.update(self._extract_go_dependencies(file_path, content, file_dir))
        elif language == 'rust':
            dependencies.update(self._extract_rust_dependencies(file_path, content, file_dir))
        elif language == 'php':
            dependencies.update(self._extract_php_dependencies(file_path, content, file_dir))
        elif language == 'ruby':
            dependencies.update(self._extract_ruby_dependencies(file_path, content, file_dir))
        elif language == 'csharp':
            dependencies.update(self._extract_csharp_dependencies(file_path, content, file_dir))
        elif language == 'html':
            dependencies.update(self._extract_html_dependencies(file_path, content, file_dir))
        elif language in ['css', 'scss', 'sass', 'less']:
            dependencies.update(self._extract_css_dependencies(file_path, content, file_dir))
        elif language == 'sql':
            dependencies.update(self._extract_sql_dependencies(file_path, content, file_dir))
        elif language == 'solidity':
            dependencies.update(self._extract_solidity_dependencies(file_path, content, file_dir))
        elif language == 'dockerfile':
            dependencies.update(self._extract_dockerfile_dependencies(file_path, content, file_dir))
        elif language == 'terraform':
            dependencies.update(self._extract_terraform_dependencies(file_path, content, file_dir))
        elif language in ['yaml', 'yml']:
            dependencies.update(self._extract_yaml_dependencies(file_path, content, file_dir))
        elif language == 'json':
            dependencies.update(self._extract_json_dependencies(file_path, content, file_dir))
        
        return dependencies
    
    def _extract_python_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module
                    level = node.level
                    if level > 0:
                        rel_path = "." * level + (f".{module}" if module else "")
                        rel_module = self.resolve_relative_import(file_dir, rel_path)
                        if rel_module:
                            dependencies.add(rel_module)
                    elif module:
                        dependencies.add(module)
        except Exception as e:
            print(f"Error parsing Python file {file_path}: {e}")
        return dependencies
    
    def _extract_js_ts_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        imports = re.findall(r'import\s+(?:[^\'"`]+\s+from\s+)?[\'"`]([^\'"`]+)[\'"`]', content)
        dependencies.update(imports)
        
        requires = re.findall(r'require\s*\(\s*[\'"`]([^\'"`]+)[\'"`]\s*\)', content)
        dependencies.update(requires)
        
        dynamic_imports = re.findall(r'import\s*\(\s*[\'"`]([^\'"`]+)[\'"`]\s*\)', content)
        dependencies.update(dynamic_imports)
        
        return dependencies
    
    def _extract_java_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()

        imports = re.findall(r'import\s+(?:static\s+)?([^;]+);', content)
        dependencies.update(imports)
        
        return dependencies
    
    def _extract_go_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        imports = re.findall(r'import\s+[\'"`]([^\'"`]+)[\'"`]', content)
        dependencies.update(imports)
        
        import_blocks = re.findall(r'import\s*\(\s*((?:[^)]*\n)*)[^)]*\)', content, re.MULTILINE)
        for block in import_blocks:
            block_imports = re.findall(r'[\'"`]([^\'"`]+)[\'"`]', block)
            dependencies.update(block_imports)
        
        return dependencies
    
    def _extract_rust_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        uses = re.findall(r'use\s+([^;]+);', content)
        dependencies.update(uses)
        
        extern_crates = re.findall(r'extern\s+crate\s+([^;]+);', content)
        dependencies.update(extern_crates)
        
        return dependencies
    
    def _extract_php_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        includes = re.findall(r'(?:include|require)(?:_once)?\s*\(?[\'"`]([^\'"`]+)[\'"`]\)?;', content)
        dependencies.update(includes)
        
        uses = re.findall(r'use\s+([^;]+);', content)
        dependencies.update(uses)
        
        return dependencies
    
    def _extract_ruby_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        requires = re.findall(r'require\s+[\'"`]([^\'"`]+)[\'"`]', content)
        dependencies.update(requires)
        
        require_relatives = re.findall(r'require_relative\s+[\'"`]([^\'"`]+)[\'"`]', content)
        dependencies.update(require_relatives)
        
        return dependencies
    
    def _extract_csharp_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        usings = re.findall(r'using\s+([^;]+);', content)
        dependencies.update(usings)
        
        return dependencies
    
    def _extract_html_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        includes = re.findall(r'{%\s*(?:include|extends)\s+[\'"]([^\'"]+)[\'"]\s*%}', content)
        dependencies.update(includes)
        
        css_links = re.findall(r'<link[^>]+href=[\'"]([^\'"]+\.css)[\'"]', content, re.IGNORECASE)
        dependencies.update(css_links)
        
        js_sources = re.findall(r'<script[^>]+src=[\'"]([^\'"]+\.js)[\'"]', content, re.IGNORECASE)
        dependencies.update(js_sources)
        
        img_sources = re.findall(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', content, re.IGNORECASE)
        dependencies.update(img_sources)
        
        return dependencies
    
    def _extract_css_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        imports = re.findall(r'@import\s+[\'"]([^\'"]+)[\'"]', content)
        dependencies.update(imports)
        
        urls = re.findall(r'url\([\'"]?([^\'")\s]+)[\'"]?\)', content)
        dependencies.update(urls)
        
        return dependencies
    
    def _extract_sql_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        tables = re.findall(r'FROM\s+(\w+)', content, re.IGNORECASE)
        dependencies.update(tables)
        
        joins = re.findall(r'JOIN\s+(\w+)', content, re.IGNORECASE)
        dependencies.update(joins)
        
        return dependencies
    
    def _extract_solidity_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        imports = re.findall(r'import\s+[\'"]([^\'"]+)[\'"]', content)
        dependencies.update(imports)
        
        inherits = re.findall(r'contract\s+\w+\s+is\s+([^{]+)', content)
        for inherit_list in inherits:
            contracts = [c.strip() for c in inherit_list.split(',')]
            dependencies.update(contracts)
        
        return dependencies
    
    def _extract_dockerfile_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        froms = re.findall(r'FROM\s+([^\s]+)', content, re.IGNORECASE)
        dependencies.update(froms)
        
        copies = re.findall(r'(?:COPY|ADD)\s+([^\s]+)', content, re.IGNORECASE)
        dependencies.update(copies)
        
        return dependencies
    
    def _extract_terraform_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        modules = re.findall(r'source\s*=\s*[\'"]([^\'"]+)[\'"]', content)
        dependencies.update(modules)
        
        return dependencies
    
    def _extract_yaml_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        images = re.findall(r'image:\s*[\'"]?([^\'">\s]+)[\'"]?', content)
        dependencies.update(images)
        
        return dependencies
    
    def _extract_json_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        
        try:
            data = json.loads(content)
            
            if isinstance(data, dict):
                for dep_type in ['dependencies', 'devDependencies', 'peerDependencies']:
                    if dep_type in data:
                        dependencies.update(data[dep_type].keys())
        except json.JSONDecodeError:
            pass
        
        return dependencies

    def resolve_relative_import(self, file_dir: str, rel_path: str) -> Optional[str]:
        parts = file_dir.split(os.sep)
        rel_depth = rel_path.count('.')
        module_name = rel_path.lstrip('.')
        
        base_parts = parts[:-rel_depth] if rel_depth > 0 else parts
        if module_name:
            base_parts.append(module_name.replace('.', os.sep))
        
        resolved_path = os.path.join(*base_parts)
        if not resolved_path.endswith('.py'):
            resolved_path += '.py'
        
        return resolved_path if os.path.exists(resolved_path) else None
    
    def get_dependencies(self, file_path: str) -> List[str]: 
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        return list(self.graph.predecessors(file_path))
    
    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)
    
    def get_language_stats(self) -> Dict[str, int]:
        stats = {}
        for node in self.graph.nodes:
            ext = Path(node).suffix.lower()
            language = self.supported_extensions.get(ext, 'unknown')
            stats[language] = stats.get(language, 0) + 1
        return stats
    
    def find_circular_dependencies(self) -> List[List[str]]:
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except nx.NetworkXError:
            return []
    
    def get_dependency_depth(self, file_path: str) -> int:
        try:
            paths = nx.single_source_shortest_path_length(self.graph, file_path)
            return max(paths.values()) if paths else 0
        except nx.NetworkXError:
            return 0
    
    def visualize_graph(self):
        try:
            import matplotlib.pyplot as plt
            pos = nx.spring_layout(self.graph)
            nx.draw(self.graph, pos, with_labels=True, arrows=True, 
                   node_size=2000, node_color='lightblue', font_size=8, 
                   font_color='black', edge_color='gray')
            plt.title("Dependency Graph")
            plt.show()
        except ImportError:
            print("matplotlib is not installed. Skipping graph visualization. please don't irritate, just install through atleast pip install -r requirements.txt")