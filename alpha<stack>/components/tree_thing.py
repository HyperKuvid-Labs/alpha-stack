import pathlib
import os
import uuid
import graphviz
# import google.generativeai as genai
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

def generate_tree(resp: str, project_name: str = "root") -> TreeNode:
    content = resp.strip().replace('```', '').strip()
    lines = content.split('\n')
    stack = []
    root = TreeNode(project_name)

    for line in lines:
        if not line.strip():
            continue

        indent = 0
        temp_line = line

        while temp_line.startswith('│   ') or temp_line.startswith('    ') or temp_line.startswith('│ ') or temp_line.startswith('    '):
            temp_line = temp_line[4:]
            indent += 1

        name = line.strip()
        if '#' in name:
            name = name.split('#')[0].strip()
        name = name.replace('│', '').replace('├──', '').replace('└──', '').strip()

        if not name or name == project_name:
            continue

        node = TreeNode(name)

        if indent == 0:
            root.add_child(node)
            stack = [root, node]
        else:
            while len(stack) > indent + 1:
                stack.pop()

            if stack:
                stack[-1].add_child(node)
            stack.append(node)

    def mark_files_and_dirs(node: TreeNode):
        if not node.children:
            node.is_file = True
        else:
            node.is_file = False
            for child in node.children:
                mark_files_and_dirs(child)

    mark_files_and_dirs(root)
    return root

def tree_to_graphviz(node, graph=None, parent_id=None):
    if graph is None:
        graph = graphviz.Digraph(comment='File Tree')
        graph.attr(rankdir='TB')
    
    node_id = str(id(node))
    
    if node.is_file:
        graph.node(node_id, node.value, shape='box', style='filled', fillcolor='lightblue')
    else:
        graph.node(node_id, node.value, shape='folder', style='filled', fillcolor='lightgreen')
    
    if parent_id:
        graph.edge(parent_id, node_id)
    
    for child in node.children:
        tree_to_graphviz(child, graph, node_id)
    
    return graph

def generate_fs(project_name : str):
    path = pathlib.Path(os.getcwd()) / "docs" / "folder_structure.md"
    content = ""
    if path.exists():
        with open(path, "r") as f:
            content = f.read()

    else:
        print("Folder structure file not found at:", path)
        return None
    
    #okay for project name i wanna think...
    #so let me go through the reqs and ts md file and get the project name
    # path1 = pathlib.Path(os.getcwd()) / "docs" / "requirements.md"
    # if path1.exists():
    #     with open(path1, "r") as f:
    #         content1 = f.read()
    #         project_name = content1.split('\n')[0].strip()
    # else:
    #     print("Requirements file not found at:", path1)
    #     project_name = "root"
    #this was useless, i will just use the project name from the ts file
    
    print("Generating file system tree from content...")
    tree = generate_tree(content, project_name="root")
    print("File system tree generated successfully.")
    path = pathlib.Path(os.getcwd()) / "docs" / "folder_structure_tree.md"
    # path.parent.mkdir(parents=True, exist_ok=True)
    # with open(path, "w") as f:
    #     f.write(f"# File System Tree for {project_name}\n\n")
    #     tree.print_tree()
    # print("File system tree saved to:", path)
    # print("Tree structure:")
    # tree.print_tree()
    # print("DFS Traversal:")
    # tree.dfsTraverse()
    print("Creating visual representation...")
    graph = tree_to_graphviz(tree)  # or use any other method above
    graph.render(f'docs/{project_name}_tree_visual', format='png', cleanup=True)
    return tree