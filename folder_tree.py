import os
import json
import re
import ast
from dotenv import load_dotenv
import matplotlib.pyplot as pl
import networkx as nx
from typing import List,Set
from pathlib import Path
import matplotlib.pyplot as plt
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
    # --- Python ---
    '.py': 'python',
    '.pyi': 'python',

    # --- JavaScript / TypeScript ---
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',

    # --- JVM / JVM languages ---
    '.java': 'java',
    '.kt': 'jvm',
    '.kts': 'jvm',
    '.scala': 'jvm',
    '.groovy': 'jvm',

    # --- PHP ---
    '.php': 'php',
    '.phtml': 'php',

    # --- Systems languages ---
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

    # --- Ruby / BEAM languages ---
    '.rb': 'ruby',
    '.ex': 'elixir',
    '.exs': 'elixir',
    '.erl': 'erlang',

    # --- Markup / Templating ---
    '.html': 'html',
    '.htm': 'html',
    '.xhtml': 'html',
    '.xml': 'xml',
    '.svg': 'svg',
    '.xsl': 'xslt',

    # --- Stylesheets ---
    '.css': 'css',
    '.scss': 'scss',
    '.sass': 'sass',
    '.less': 'less',
    '.styl': 'stylus',

    # --- Config / Data ---
    '.json': 'json',
    '.yml': 'yaml',
    '.yaml': 'yaml',
    '.toml': 'toml',
    '.ini': 'ini',
    '.env': 'dotenv',
    '.env.example': 'dotenv',

    # --- Shell / Build ---
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

    # --- Documentation ---
    '.md': 'markdown',
    '.rst': 'restructuredtext',
    '.txt': 'text',
    '.adoc': 'asciidoc',
    '.asciidoc': 'asciidoc',

    # --- Databases ---
    '.sql': 'sql',
    '.sqlite': 'sqlite',
    '.db': 'database',
    '.migration': 'migration',
    # --- Infra / CI-CD ---
    '.dockerfile': 'dockerfile',
    '.tf': 'terraform',
    '.hcl': 'terraform',
    '.circleci': 'circleci',
    '.gitlab-ci.yml': 'gitlab-ci',
    '.jenkins': 'jenkins',
    '.travis.yml': 'travis',

    # --- Smart contracts / Blockchain ---
    '.sol': 'solidity',
    '.vy': 'vyper',
    '.cairo': 'cairo',
    '.move': 'move',
    '.clar': 'clarity',

    # --- Framework-specific ---
    '.vue': 'vue',
    '.svelte': 'svelte',
    '.dart': 'dart',

    # --- Misc config / security ---
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

    def add_file(self, file_path: str, content: str,folder_structure:str):
        self.graph.add_node(file_path)
        dependencies = self.extract_dependencies(file_path, content,folder_structure)
        for dep in dependencies:
            self.graph.add_edge(file_path, dep)
    
    def extract_dependencies(self, file_path: str, content: str,folder_structure:str,) -> Set[str]:
        dependencies = set()
        file_dir = os.path.dirname(file_path)
        file_ext = Path(file_path).suffix.lower()
        #yet to complete it have switch betweeen dialama
              
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
        elif language == 'jvm':
            dependencies.update(self._extract_jvm_dependencies(file_path, content, file_dir))
        elif language in ['c','cpp','c-header','cpp-header']:
            dependencies.update(self._extract_c_cpp_dependencies(file_path, content, file_dir))
        elif language == "objective-c":
            dependencies.update(self._extract_objc_dependencies(file_path, content, file_dir))
        elif language == "swift":
            dependencies.update(self._extract_swift_dependencies(file_path, content, file_dir))
        
        return dependencies
    def _extract_objc_dependencies(self, file_path: str, content: str, file_dir: str) -> Set[str]:
       dependencies = set()
       # #import or #include
       imports = re.findall(r'#(?:import|include)\s*[<"]([^">]+)[">]', content)
       dependencies.update(imports)
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
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        return list(self.graph.predecessors(file_path))
    
    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)
    
    def visualize_graph(self):
        try:
            pos = nx.spring_layout(self.graph)
            nx.draw(self.graph, pos, with_labels=True, arrows=True, node_size=2000, node_color='lightblue', font_size=10, font_color='black', edge_color='gray')
            pl.title("Dependency Graph")
            pl.show()
        except ImportError:
            print("matplotlib is not installed. Skipping graph visualization.")
