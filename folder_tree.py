import os
import json
import re
import ast
from google import genai
from google.genai import types
from dotenv import load_dotenv
import matplotlib.pyplot as pl
import networkx as nx
from typing import List,Set
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

    def add_file(self, file_path: str, content: str,folder_structure:str):
        self.graph.add_node(file_path)
        dependencies = self.extract_dependencies(file_path, content,folder_structure)
        for dep in dependencies:
            self.graph.add_edge(file_path, dep)
    
    def extract_dependencies(self, file_path: str, content: str,folder_structure:str,) -> Set[str]:
        dependencies = set()
        file_dir = os.path.dirname(file_path)
        #yet to complete it have switch betweeen dialama
        client = get_client()
        
        json_output={
        "library_name_1",
        "library_name_2",
        "/resolved/relative/path/to/file1.js",
        "/resolved/realtive/path/to/another/file2.py"}
        prompt=f"""You are a specialized code analysis agent. Your task is to parse a given source code file, identify all its dependencies, and categorize them as either external libraries or internal project files. You must resolve all relative file paths to their absolute paths"from the project root.
        You will be provided with the following information:
        LANGUAGE: The programming language of the code (e.g., 'Python', 'JavaScript', 'Java', 'Dart').        
        PROJECT_STRUCTURE: A string representation of the entire project's folder and file tree.
        FILE_PATH: The absolute path of the file being analyzed, relative to the project root (e.g., /src/components/TaskList.js).
        FILE_CONTENT: The complete source code of the file as a string.
        Your task is to perform the following steps:
        Analyze the FILE_CONTENT to find all import statements (e.g., import, require, from ... import, include etc).(modules and other files in the project)
        If the import refers to a standard, built-in, or third-party library that is not a file within the provided PROJECT_STRUCTURE (e.g., 'react', 'pandas', 'java.util.Scanner').
        the import refers to another file within the project, typically using a relative path (e.g., ../utils/helpers, ./api, ../../config).
        Resolve all relative paths: For every import categorized as a file, use the FILE_PATH as the starting point to calculate its full, absolute path from the project root.
        For example, if FILE_PATH is /FrontEnd/src/components/Task/TaskItem.jsx and an import is ../../api.js, the resolved absolute path is /FrontEnd/src/api.js.
        Output Specification:You MUST respond with only a single, raw JSON object and nothing else. No explanations or introductory text. The JSON object must have the following structure:
        JSON
        {json_output}
        <project_strcutre>
        {folder_structure}
        </project_strcutre>
        <content>
        {content}
        </content>
        <file_path>
        {file_path}
        </file_path>
        the output shoulbd contain only the dictionary nothing else sholbd eb there in the output like dont add the tag like json in the output im making that clear"""
        resp = client.models.generate_content(model="gemini-2.5-flash-preview-05-20", contents=prompt)
        dependencies= ast.literal_eval(resp.text)
        pf=True
        for dep in dependencies:
            if not re.search(re.escape(dep), content):
                pf = False
                break
        if not pf:
            print("avolodha")
        return dependencies
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
            pos = nx.spring_layout(self.graph)
            nx.draw(self.graph, pos, with_labels=True, arrows=True, node_size=2000, node_color='lightblue', font_size=10, font_color='black', edge_color='gray')
            pl.title("Dependency Graph")
            pl.show()
        except ImportError:
            print("matplotlib is not installed. Skipping graph visualization.")
