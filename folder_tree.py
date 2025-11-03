import os
import json
import re
import ast
from dotenv import load_dotenv
import networkx as nx
from typing import Dict, List, Optional, Set
from pathlib import Path
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader
from genai_client import get_client
class TreeNode:
    def __init__(self, value):
        self.value = value
        self.children = []
        self.is_file = False

    def add_child(self, child_node):
        print("Adding child node:", child_node.value)
        self.children.append(child_node)
    
    def print_tree(self, level=0, prefix=""):
        if level == 0:
            print(self.value)
        else:
            print(prefix + "├── " + self.value)
        
        for i, child in enumerate(self.children):
            is_last = i == len(self.children) - 1
            child.print_tree(
                level + 1, 
                prefix + ("    " if is_last else "│   ")
            )

    def dfsTraverse(self):
        print("Current node value: ", self.value)
        for child in self.children:
            child.dfsTraverse()

class DependencyAnalyzer:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.supported_extensions = {
    '.py': 'python',
    '.pyi': 'python',

    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',

    '.java': 'java',
    '.kt': 'jvm',
    '.kts': 'jvm',
    '.scala': 'jvm',
    '.groovy': 'jvm',

    '.php': 'php',
    '.phtml': 'php',

    '.rs': 'rust',
    '.go': 'go',
    '.c': 'c',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.h': 'c-header',
    '.hpp': 'cpp-header',
    '.cs': 'csharp',
    '.m': 'objective-c',
    '.mm': 'objective-c',
    '.swift': 'swift',

    '.rb': 'ruby',
    '.ex': 'elixir',
    '.exs': 'elixir',
    '.erl': 'erlang',

    '.html': 'html',
    '.htm': 'html',
    '.xhtml': 'html',
    '.xml': 'xml',
    '.svg': 'svg',
    '.xsl': 'xslt',

    '.css': 'css',
    '.scss': 'scss',
    '.sass': 'sass',
    '.less': 'less',
    '.styl': 'stylus',

    '.json': 'json',
    '.yml': 'yaml',
    '.yaml': 'yaml',
    '.toml': 'toml',
    '.ini': 'ini',
    '.env': 'dotenv',
    '.env.example': 'dotenv',

    '.sh': 'shell',
    '.bash': 'shell',
    '.zsh': 'shell',
    '.fish': 'shell',
    '.bat': 'batch',
    '.cmd': 'batch',
    '.ps1': 'powershell',
    '.mk': 'makefile',
    '.make': 'makefile',
    '.cmake': 'cmake',
    '.gradle': 'gradle',
    '.mvn': 'maven',

    '.md': 'markdown',
    '.rst': 'restructuredtext',
    '.txt': 'text',
    '.adoc': 'asciidoc',
    '.asciidoc': 'asciidoc',

    '.sql': 'sql',
    '.sqlite': 'sqlite',
    '.db': 'database',
    '.migration': 'migration',
    '.dockerfile': 'dockerfile',
    '.tf': 'terraform',
    '.hcl': 'terraform',
    '.circleci': 'circleci',
    '.gitlab-ci.yml': 'gitlab-ci',
    '.jenkins': 'jenkins',
    '.travis.yml': 'travis',

    '.sol': 'solidity',
    '.vy': 'vyper',
    '.cairo': 'cairo',
    '.move': 'move',
    '.clar': 'clarity',

    '.vue': 'vue',
    '.svelte': 'svelte',
    '.dart': 'dart',

    '.lock': 'lockfile',
    '.plist': 'plist',
    '.conf': 'config',
    '.cfg': 'config',
    '.properties': 'properties',
    '.pem': 'certificate',
    '.crt': 'certificate',
    '.csr': 'certificate',
    '.key': 'private-key',
    '.pub': 'public-key'}
        self.project_root: Optional[str] = None
        self.project_files: Set[str] = set()
        self.dependency_details: Dict[str, List[Dict[str, Optional[str]]]] = {}
        self.ai_resolution_cache: Dict[str, Dict] = {}  # Cache for AI resolution results
        # Setup Jinja2 environment for templates - use prompts directory
        template_dir = os.path.join(os.path.dirname(__file__), 'prompts')
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def add_file(self, file_path: str, content: str,folder_structure:str):
        abs_path = os.path.abspath(file_path)
        self.project_files.add(abs_path)
        self._update_project_root()

        self.graph.add_node(abs_path)
        outgoing = list(self.graph.out_edges(abs_path))
        if outgoing:
            self.graph.remove_edges_from(outgoing)

        file_ext = Path(abs_path).suffix.lower()
        language = self.supported_extensions.get(file_ext, 'unknown')
        dependencies = self.extract_dependencies(abs_path, content,folder_structure, language)

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
        self._refresh_existing_dependencies()
    
    def extract_dependencies(self, file_path: str, content: str,folder_structure:str, language: Optional[str] = None) -> Set[str]:
        dependencies = set()
        file_dir = os.path.dirname(file_path)
        file_ext = Path(file_path).suffix.lower()

        language = language or self.supported_extensions.get(file_ext, 'unknown')
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
        elif language == 'jvm':
            dependencies.update(self._extract_jvm_dependencies(file_path, content, file_dir))
        elif language in ['c','cpp','c-header','cpp-header']:
            dependencies.update(self._extract_c_cpp_dependencies(file_path, content, file_dir))
        elif language == "objective-c":
            dependencies.update(self._extract_objc_dependencies(file_path, content, file_dir))
        elif language == "swift":
            dependencies.update(self._extract_swift_dependencies(file_path, content, file_dir))

        return dependencies

    def _update_project_root(self) -> None:
        if not self.project_files:
            return
        try:
            self.project_root = os.path.commonpath(list(self.project_files))
        except ValueError:
            # Occurs if files are on different drives; ignore in that scenario
            pass

    def _classify_dependency(self, source_path: str, raw_dep: str, language: str) -> Dict[str, Optional[str]]:
        """
        Generic dependency classifier that works for ALL languages.
        Uses a universal relative path resolver instead of language-specific logic.
        """
        raw_dep = raw_dep.strip()
        if not raw_dep:
            return {"raw": raw_dep, "kind": "external"}

        resolved_path = self._resolve_relative_path(source_path, raw_dep)

        if resolved_path and os.path.isfile(resolved_path):
            return {
                "raw": raw_dep,
                "kind": "internal",
                "path": os.path.abspath(resolved_path)
            }

        return {
            "raw": raw_dep,
            "kind": "external"
        }

    def _resolve_relative_path(self, source_path: str, raw_dep: str) -> Optional[str]:
        if not raw_dep:
            return None
        
        raw_dep = raw_dep.strip()
        
        if not (raw_dep.startswith('.') or raw_dep.startswith('/')):
            return None
        
        base_dir = os.path.dirname(source_path)
        
        if raw_dep.startswith('./'):
            rel_path = raw_dep[2:]
            target_path = os.path.join(base_dir, rel_path)
            return self._resolve_file_path(target_path, source_path)
        
        if raw_dep.startswith('.') and not raw_dep.startswith('./'):
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
        
        return None
    
    def _resolve_file_path(self, base_path: str, source_path: str) -> Optional[str]:
        """
        Generic file path resolver that works for all languages.
        Tries to find the file with common extensions based on source file type.
        """
        source_ext = Path(source_path).suffix.lower()
        
        # Normalize path
        base_path = os.path.normpath(base_path)
        
        # If path already has extension and file exists, return it
        if os.path.isfile(base_path):
            return os.path.abspath(base_path)
        
        # Get possible extensions based on source file type
        possible_extensions = self._get_possible_extensions(source_ext)
        
        # Try with source file's extension first
        if source_ext:
            candidate = base_path + source_ext
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)
        
        # Try all possible extensions
        for ext in possible_extensions:
            candidate = base_path + ext
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)
        
        # Try as directory with index file
        if os.path.isdir(base_path):
            for ext in possible_extensions:
                index_file = os.path.join(base_path, 'index' + ext)
                if os.path.isfile(index_file):
                    return os.path.abspath(index_file)
                # For Python, try __init__.py
                if ext == '.py':
                    init_file = os.path.join(base_path, '__init__.py')
                    if os.path.isfile(init_file):
                        return os.path.abspath(init_file)
        
        return None
    
    def _get_possible_extensions(self, source_ext: str) -> List[str]:
        """
        Get possible file extensions based on source file extension.
        This helps resolve dependencies across languages.
        """
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
            '.m': ['.m', '.h'],
            '.mm': ['.mm', '.m', '.h'],
            '.cpp': ['.cpp', '.c', '.hpp', '.h'],
            '.c': ['.c', '.h'],
            '.html': ['.html', '.htm'],
            '.css': ['.css', '.scss', '.sass', '.less'],
            '.scss': ['.scss', '.css'],
            '.vue': ['.vue'],
            '.svelte': ['.svelte'],
        }
        
        return extension_map.get(source_ext, [source_ext] if source_ext else [])


    def _refresh_existing_dependencies(self) -> None:
        for source_path, details in list(self.dependency_details.items()):
            file_ext = Path(source_path).suffix.lower()
            language = self.supported_extensions.get(file_ext, 'unknown')

            updated_details: List[Dict[str, Optional[str]]] = []
            for detail in details:
                raw_dep = detail.get('raw', '') if isinstance(detail, dict) else ''
                if raw_dep:
                    reclassified = self._classify_dependency(source_path, raw_dep, language)
                    updated_details.append(reclassified)
                else:
                    updated_details.append(detail)

            outgoing = list(self.graph.out_edges(source_path))
            if outgoing:
                self.graph.remove_edges_from(outgoing)

            for info in updated_details:
                if isinstance(info, dict) and info.get('kind') == 'internal' and info.get('path'):
                    target = os.path.abspath(info['path'])
                    self.graph.add_node(target)
                    if not self.graph.has_edge(source_path, target):
                        self.graph.add_edge(source_path, target)

            self.dependency_details[source_path] = updated_details
    def _extract_objc_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       # #import or #include
       includes = re.findall(r'#(?:import|include)\s*[<"]([^">]+)[">]', content)
       dependencies.update(includes)
       module_imports = re.findall(r'@import\s+([a-zA-Z0-9_.]+)\s*;', content)
       dependencies.update(module_imports)
   
       return dependencies
    def _extract_c_cpp_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
      dependencies = set()
  
      # Matches: #include <stdio.h>  OR  #include "myheader.h"
      includes = re.findall(r'^\s*#\s*include\s*[<"]([^">]+)[">]', content, flags=re.MULTILINE)
      for inc in includes:
          # Split in case of malformed comma-separated includes
          for part in inc.split(","):
              dependencies.add(part.strip())
  
      return dependencies
    def _extract_csharp_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
   
       # using System.Text;   OR   using alias = Namespace.Type;
       usings = re.findall(r'^\s*using\s+(?:([A-Za-z0-9_]+)\s*=\s*)?([A-Za-z0-9_.]+)\s*;', content, flags=re.MULTILINE)
       for alias, dep in usings:
           dependencies.add(dep.strip())
   
       # extern alias MyAlias;
       externs = re.findall(r'^\s*extern\s+alias\s+([A-Za-z0-9_]+)\s*;', content, flags=re.MULTILINE)
       for dep in externs:
           dependencies.add(dep.strip())
   
       return dependencies
    def _extract_objc_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
   
       # #import <Foundation/Foundation.h>  OR  #include "MyHeader.h"
       includes = re.findall(r'^\s*#\s*(?:import|include)\s*[<"]([^">]+)[">]', content, flags=re.MULTILINE)
       for inc in includes:
           for part in inc.split(","):
               dependencies.add(part.strip())
   
       # @import Foundation;  OR  @import UIKit.UIColor;
       module_imports = re.findall(r'^\s*@import\s+([A-Za-z0-9_.]+)\s*;', content, flags=re.MULTILINE)
       for imp in module_imports:
           for part in imp.split(","):
               dependencies.add(part.strip())
   
       return dependencies
    def _extract_swift_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       imports = re.findall(
           r'^\s*(?:@[_a-zA-Z0-9]+\s+)*import\s+'
           r'(?:class|struct|enum|protocol|func|var|typealias\s+)?'
           r'([A-Za-z0-9_.]+(?:\s*,\s*[A-Za-z0-9_.]+)*)'
           r'(?:\s+as\s+[A-Za-z0-9_]+)?',
           content,
           flags=re.MULTILINE
       )
   
       for imp in imports:
           for part in imp.split(","):
               dependencies.add(part.strip())
   
       return dependencies
    def _extract_jvm_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       # Match any import line (Java, Kotlin, Scala, Groovy)
       raw_imports = re.findall(
           r'^\s*import\s+(?:static\s+)?([a-zA-Z0-9_.*{},\s=>\\]+)(?:\s+as\s+[A-Za-z0-9_]+)?;?',
           content,
           flags=re.MULTILINE
       )
       for imp in raw_imports:
           imp = imp.strip()
           # Case 1: Scala grouped imports {A, B, C}
           if '{' in imp and '}' in imp:
               prefix, group = imp.split('{', 1)
               prefix = prefix.strip().rstrip('.')
               group = group.strip('}').strip()
               parts = [p.strip() for p in group.split(',')]
               for p in parts:
                   # Handle rename => JDate
                   if '=>' in p:
                       left, _ = [x.strip() for x in p.split('=>')]
                       dependencies.add(f"{prefix}.{left}")
                   else:
                       dependencies.add(f"{prefix}.{p}")
           # Case 2: Scala rename (no braces): Date => JDate
           elif '=>' in imp:
               left, _ = [x.strip() for x in imp.split('=>')]
               dependencies.add(left)
           # Case 3: Kotlin/Groovy alias (as)
           elif ' as ' in imp:
               base, _ = imp.split(' as ', 1)
               dependencies.add(base.strip())
           # Case 4: Normal / wildcard imports
           else:
               dependencies.add(imp)
   
       return dependencies
       
    def _extract_go_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
      dependencies = set()
      imports = re.findall(r'import\s+(?:[a-zA-Z0-9_]+\s+)?["]([^"]+)["]', content)
      dependencies.update(imports)
  
      block_imports = re.findall(r'import\s*\((.*?)\)', content, flags=re.DOTALL)
      for block in block_imports:
          matches = re.findall(r'"([^"]+)"', block)
          dependencies.update(matches)
  
      return dependencies
    def _extract_java_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       imports = re.findall(r'^\s*import\s+(?:static\s+)?([a-zA-Z0-9_.*]+);', content, flags=re.MULTILINE)
       dependencies.update(imports)
       return dependencies
    def _extract_ruby_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       requires = re.findall(r'require\s+[\'"]([^\'"]+)[\'"]', content)
       dependencies.update(requires)
   
       require_rel = re.findall(r'require_relative\s+[\'"]([^\'"]+)[\'"]', content)
       dependencies.update(require_rel)
   
       loads = re.findall(r'load\s+[\'"]([^\'"]+)[\'"]', content)
       dependencies.update(loads)
   
       return dependencies
    def _extract_php_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       includes = re.findall(r'\b(?:include|require|include_once|require_once)\s*\(?\s*[\'"]([^\'"]+)[\'"]\)?', content)
       dependencies.update(includes)
   
       uses = re.findall(r'\buse\s+([a-zA-Z0-9_\\]+);', content)
       dependencies.update(uses)
   
       return dependencies
    def _extract_rust_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        externs = re.findall(r'extern\s+crate\s+([a-zA-Z0-9_]+);', content)
        dependencies.update(externs)
    
        uses = re.findall(r'\buse\s+([a-zA-Z0-9_:{}*,\s]+);', content)
        dependencies.update([u.strip() for u in uses])
    
        mods = re.findall(r'\b(?:mod|pub\s+mod)\s+([a-zA-Z0-9_]+);', content)
        dependencies.update(mods)
    
        return dependencies
    def _extract_html_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        dependencies.update(scripts)
        links = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        dependencies.update(links)
        images = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        dependencies.update(images)
        media = re.findall(r'<(?:video|audio|source)[^>]+src=["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        dependencies.update(media)
        frames = re.findall(r'<(?:iframe|embed)[^>]+src=["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        dependencies.update(frames)
        inline_styles = re.findall(r'style=["\'][^"\']*url\(([^)]+)\)[^"\']*["\']', content, flags=re.IGNORECASE)
        dependencies.update(inline_styles)

        return dependencies

    def _extract_css_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        css_imports = re.findall(r'@import\s+(?:url\()?["\']([^"\']+)["\']\)?', content, flags=re.IGNORECASE)
        dependencies.update(css_imports)
        scss_uses = re.findall(r'@use\s+["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        dependencies.update(scss_uses)
        scss_forwards = re.findall(r'@forward\s+["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        dependencies.update(scss_forwards)
        less_imports = re.findall(r'@import\s*(?:\([^)]*\)\s*)?["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        dependencies.update(less_imports)
        urls = re.findall(r'url\((["\']?)([^)\'"]+)\1\)', content, flags=re.IGNORECASE)
        dependencies.update([u[1] for u in urls])
        return dependencies
    def _extract_python_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       imports = re.findall(r'^\s*import\s+([a-zA-Z_][\w\.]*)', content)
       dependencies.update(imports)
       from_imports = re.findall(r'^\s*from\s+([a-zA-Z_][\w\.]*)\s+import', content)
       dependencies.update(from_imports)
       relative_imports = re.findall(r'^\s*from\s+(\.+[a-zA-Z_][\w\.]*)\s+import', content)
       dependencies.update(relative_imports)
       importlib_imports = re.findall(r'importlib\.import_module\(\s*[\'"]([a-zA-Z_][\w\.]*)[\'"]\s*\)', content)
       dependencies.update(importlib_imports)
       dunder_imports = re.findall(r'__import__\(\s*[\'"]([a-zA-Z_][\w\.]*)[\'"]\s*\)', content)
       dependencies.update(dunder_imports)
       return dependencies
    def _extract_js_ts_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
      dependencies = set()
      es6_imports = re.findall(r'import\s+(?:[\w{}\*\s,]+?\s+from\s+)?[\'"]([^\'"]+)[\'"]', content)
      dependencies.update(es6_imports)
      requires = re.findall(r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content)
      dependencies.update(requires)
      dynamic_imports = re.findall(r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content)
      dependencies.update(dynamic_imports)
      json_imports = re.findall(r'import\s+[^\'"`]+\s+from\s+[\'"`]([^\'"`]+\.json)[\'"`]\s+assert', content)
      dependencies.update(json_imports)
      return dependencies
    def _extract_dockerfile_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        froms = re.findall(r'^\s*FROM\s+([^\s]+)', content, flags=re.IGNORECASE | re.MULTILINE)
        dependencies.update(froms)
        copies = re.findall(r'^\s*(?:COPY|ADD)\s+([^\s]+)', content, flags=re.IGNORECASE | re.MULTILINE)
        dependencies.update(copies)
        pkgs = re.findall(r'apt-get\s+install\s+-y\s+([^\n]+)', content)
        dependencies.update(pkgs)
        pip_pkgs = re.findall(r'pip\s+install\s+([^\n]+)', content)
        dependencies.update(pip_pkgs)

        return dependencies
    def _extract_solidity_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        return set(re.findall(r'import\s+["\']([^"\']+)["\']', content))
    def _extract_terraform_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        modules = re.findall(r'source\s*=\s*["\']([^"\']+)["\']', content)
        dependencies.update(modules)
        providers = re.findall(r'provider\s+"([^"]+)"', content)
        dependencies.update(providers)
        req_providers = re.findall(r'required_providers\s*{([^}]*)}', content, flags=re.DOTALL)
        for block in req_providers:
            provs = re.findall(r'([a-zA-Z0-9_-]+)\s*=\s*{', block)
            dependencies.update(provs)
        return dependencies
    def _extract_yaml_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        includes = re.findall(r'^\s*(?:include|import|extends):\s*["\']?([^"\']+)["\']?', content, flags=re.MULTILINE)
        dependencies.update(includes)
        images = re.findall(r'^\s*image:\s*["\']?([^"\']+)["\']?', content, flags=re.MULTILINE)
        dependencies.update(images)
        builds = re.findall(r'^\s*build:\s*["\']?([^"\']+)["\']?', content, flags=re.MULTILINE)
        dependencies.update(builds)

        return dependencies
    def _extract_json_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
        dependencies = set()
        deps = re.findall(r'"(?:dependencies|devDependencies)"\s*:\s*{([^}]*)}', content, flags=re.DOTALL)
        for block in deps:
            pkgs = re.findall(r'"([^"]+)"\s*:', block)
            dependencies.update(pkgs)
        includes = re.findall(r'"(?:import|include|extends)"\s*:\s*"([^"]+)"', content)
        dependencies.update(includes)
        images = re.findall(r'"image"\s*:\s*"([^"]+)"', content)
        dependencies.update(images)
        return dependencies
    def _extract_sql_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       table_refs = re.findall(
        r'\bFROM\s+([a-zA-Z0-9_\."]+)|\bJOIN\s+([a-zA-Z0-9_\."]+)', 
        content, 
        flags=re.IGNORECASE)
       for t1, t2 in table_refs:
           dependencies.add((t1 or t2).strip('"'))
       inserts = re.findall(
        r'\bINSERT\s+INTO\s+([a-zA-Z0-9_\."]+)', 
        content, 
        flags=re.IGNORECASE)
       dependencies.update([i.strip('"') for i in inserts])
       updates = re.findall(
        r'\bUPDATE\s+([a-zA-Z0-9_\."]+)', 
        content, 
        flags=re.IGNORECASE)
       dependencies.update([u.strip('"') for u in updates])
       creates = re.findall(
        r'\bCREATE\s+(?:TABLE|VIEW)\s+([a-zA-Z0-9_\."]+)', 
        content, 
        flags=re.IGNORECASE)
       dependencies.update([c.strip('"') for c in creates])
       calls = re.findall(
        r'\b(?:CALL|EXEC(?:UTE)?)\s+([a-zA-Z0-9_\."]+)', 
        content, 
        flags=re.IGNORECASE)
       dependencies.update([c.strip('"') for c in calls])
       return dependencies
    def resolve_relative_import(self, file_path: str, rel_path: str) -> str:
      file_dir = os.path.dirname(file_path)
      if os.path.isabs(rel_path):
          return os.path.normpath(rel_path)
      if rel_path.startswith("."):
          return os.path.normpath(os.path.join(file_dir, rel_path))
      return rel_path
    
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

    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)

    def _get_project_file_index(self) -> List[Dict[str, str]]:
        """Build an index of all project files with their paths and languages for AI resolver."""
        index = []
        for file_path in sorted(self.project_files):
            if not os.path.isfile(file_path):
                continue
            file_ext = Path(file_path).suffix.lower()
            language = self.supported_extensions.get(file_ext, 'unknown')
            rel_path = os.path.relpath(file_path, self.project_root) if self.project_root else file_path
            index.append({
                "path": rel_path,
                "absolute_path": file_path,
                "language": language
            })
        return index

    def _resolve_dependencies_via_agent(self, source_path: str, raw_dep: str, language: str) -> Optional[str]:
        """Use AI agent to resolve an unresolved dependency to a file path."""
        cache_key = f"{source_path}:{raw_dep}:{language}"
        if cache_key in self.ai_resolution_cache:
            cached = self.ai_resolution_cache[cache_key]
            if cached.get("resolved") and cached.get("internal"):
                resolved_paths = cached.get("resolved_paths", [])
                if resolved_paths and resolved_paths[0]:
                    return os.path.abspath(resolved_paths[0])
            return None

        try:
            project_index = self._get_project_file_index()
            if not project_index:
                return None

            template = self.jinja_env.get_template("dep_resolution_prompt.j2")
            prompt = template.render(
                source_file=os.path.relpath(source_path, self.project_root) if self.project_root else source_path,
                source_language=language,
                raw_dependency=raw_dep,
                project_root=self.project_root or "",
                project_files=project_index[:100]  # Limit to avoid token limits
            )

            client = get_client()
            resp = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt
            )
            text = resp.text or ""
            
            # Parse JSON response
            json_text = re.sub(r"```json\s*", "", text)
            json_text = re.sub(r"```\s*", "", json_text).strip()
            m = re.search(r"\{.*\}", json_text, re.DOTALL)
            if m:
                json_text = m.group(0)
            
            result = json.loads(json_text)
            
            # Cache result
            self.ai_resolution_cache[cache_key] = result
            
            if result.get("resolved") and result.get("internal"):
                resolved_paths = result.get("resolved_paths", [])
                if resolved_paths and resolved_paths[0]:
                    candidate = resolved_paths[0]
                    # Normalize path
                    if not os.path.isabs(candidate):
                        if self.project_root:
                            candidate = os.path.join(self.project_root, candidate)
                        else:
                            candidate = os.path.join(os.path.dirname(source_path), candidate)
                    candidate = os.path.abspath(os.path.normpath(candidate))
                    
                    # Verify file exists
                    if os.path.isfile(candidate):
                        return candidate
                    # Try to find file by name
                    for project_file in self.project_files:
                        if os.path.basename(project_file) == os.path.basename(candidate):
                            return os.path.abspath(project_file)
            
            return None
        except Exception as e:
            print(f"⚠️  AI resolution failed for {raw_dep} in {source_path}: {e}")
            return None

    def visualize_graph(self, output_path: Optional[str] = None) -> None:
        if not self.graph.nodes:
            print("⚠️  Dependency graph is empty. Nothing to visualize.")
            return

        if output_path:
            try:
                plt.figure(figsize=(12, 8))
                pos = nx.spring_layout(self.graph)
                nx.draw(
                    self.graph,
                    pos,
                    with_labels=True,
                    arrows=True,
                    node_size=1600,
                    node_color="#4f8ef7",
                    font_size=9,
                    font_color="white",
                    edge_color="#999999",
                    arrowstyle="->",
                    arrowsize=15,
                )
                plt.title("Dependency Graph", fontsize=14)
                plt.tight_layout()
                plt.savefig(output_path, bbox_inches="tight")
                plt.close()
                print(f"📸 Dependency graph saved to {output_path}")
            except Exception as exc:
                print(f"❌ Failed to save dependency graph visualization: {exc}")
            return

        print("\n📈 Dependency Graph Overview")
        print("=" * 80)
        for node in sorted(self.graph.nodes):
            dependents = sorted(self.graph.successors(node))
            rel_node = os.path.relpath(node, self.project_root) if self.project_root else node
            print(f"• {rel_node}")
            if dependents:
                for dep in dependents:
                    rel_dep = os.path.relpath(dep, self.project_root) if self.project_root else dep
                    print(f"   └─ {rel_dep}")
            else:
                print("   └─ (no dependencies)")