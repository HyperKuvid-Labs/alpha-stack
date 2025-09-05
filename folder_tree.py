import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv
from matplotlib import pyplot as plt
import networkx as nx
from folder_tree import DependencyAnalyzer,TreeNode
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

    def add_file(self, file_path: str, content: str):
        self.graph.add_node(file_path)
        dependencies = self.extract_dependencies(file_path, content)
        for dep in dependencies:
            self.graph.add_edge(file_path, dep)
    
    def extract_dependencies(self, file_path: str, content: str) -> Set[str]:
        dependencies = set()
        file_dir = os.path.dirname(file_path)
        #yet to complete it have switch betweeen dialama
    def resolve_relative_import(self, file_path: str, rel_path: str) -> str:
        parts = file_path.split(os.sep)
        rel_depth = rel_path.count('.')
        module_name = rel_path.replace('.', '')
        base_parts = parts[:-rel_depth]
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
    
    def visualize_graph(self):
        try:
            import matplotlib.pyplot as pl
            pos = nx.spring_layout(self.graph)
            nx.draw(self.graph, pos, with_labels=True, arrows=True, node_size=2000, node_color='lightblue', font_size=10, font_color='black', edge_color='gray')
            pl.title("Dependency Graph")
            pl.show()
        except ImportError:
            print("matplotlib is not installed. Skipping graph visualization.")
