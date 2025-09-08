#so new thing added over here is getting the description for the file nodes here, coz it makes more sense, rather than making the llm to understand and use it, so let's see if this tweak helps us, will get back when im done with the testing!!
import pathlib
import os
import uuid
import graphviz
import google.generativeai as genai

class TreeNode:
    def __init__(self, value, desc=""):
        self.value = value
        self.children = []
        self.is_file = False
        self.description = desc
        self.file_path = ""
        self.code = ""

    def add_child(self, child_node):
        print("Adding child node:", child_node.value)
        self.children.append(child_node)

    def set_description(self, description):
        self.description = description

    def print_tree(self, level=0, prefix="", show_descriptions=False):
        if level == 0:
            print(self.value)
            if show_descriptions and self.description:
                print(f"  Description: {self.description}")
        else:
            print(prefix + "├── " + self.value)
            if show_descriptions and self.description:
                print(prefix + "│   Description: " + self.description)

        for i, child in enumerate(self.children):
            is_last = i == len(self.children) - 1
            child.print_tree(
                level + 1,
                prefix + ("    " if is_last else "│   "),
                show_descriptions
            )

    def dfs_traverse_debug(self, level=0, prefix="", show_stats=True):

        indent = "  " * level
        type_indicator = "📄 FILE" if self.is_file else "📁 DIR "
        
        # Truncate description for readability
        desc_preview = ""
        if self.description:
            desc_preview = f" | {self.description[:40]}..." if len(self.description) > 40 else f" | {self.description}"
        
        # Show node information
        print(f"{indent}{type_indicator} [{level:2d}] {self.value}{desc_preview}")
        
        # Show potential issues
        issues = []
        if not self.value or self.value.strip() == "":
            issues.append("⚠️  EMPTY VALUE")
        if self.is_file and self.children:
            issues.append("⚠️  FILE HAS CHILDREN")
        if not self.is_file and not self.children and self.value != "root":
            issues.append("⚠️  EMPTY DIRECTORY")
        if "#" in self.value:
            issues.append("⚠️  CONTAINS HASH CHARACTER")
        
        if issues:
            for issue in issues:
                print(f"{indent}    {issue}")
        
        # Traverse children
        for i, child in enumerate(self.children):
            is_last = i == len(self.children) - 1
            child_prefix = prefix + ("└── " if is_last else "├── ")
            child.dfs_traverse_debug(level + 1, prefix + ("    " if is_last else "│   "), show_stats)
        
        # Show statistics at root level
        if level == 0 and show_stats:
            self._print_tree_statistics()

    def _print_tree_statistics(self):
        """Print comprehensive tree statistics"""
        total_nodes = self._count_nodes()
        file_nodes = self._count_files()
        dir_nodes = total_nodes - file_nodes
        max_depth = self._get_max_depth()
        
        print("\n" + "="*60)
        print("TREE STATISTICS")
        print("="*60)
        print(f"📊 Total Nodes: {total_nodes}")
        print(f"📁 Directories: {dir_nodes}")
        print(f"📄 Files: {file_nodes}")
        print(f"🔢 Max Depth: {max_depth}")
        print(f"🌳 Tree Structure: {'✅ BALANCED' if max_depth <= 8 else '⚠️  VERY DEEP'}")
        
        # Check for common issues
        issues_found = []
        if total_nodes < 10:
            issues_found.append("⚠️  Very few nodes - possible parsing failure")
        if file_nodes == 0:
            issues_found.append("⚠️  No files found - nothing will be generated")
        if dir_nodes > file_nodes * 2:
            issues_found.append("⚠️  Too many directories relative to files")
        
        if issues_found:
            print("\n🚨 POTENTIAL ISSUES:")
            for issue in issues_found:
                print(f"   {issue}")
        else:
            print("\n✅ Tree structure looks healthy for file generation")
        
        print("="*60)

    def _count_nodes(self):
        """Count total nodes in tree"""
        count = 1
        for child in self.children:
            count += child._count_nodes()
        return count

    def _count_files(self):
        """Count file nodes in tree"""
        count = 1 if self.is_file else 0
        for child in self.children:
            count += child._count_files()
        return count

    def _get_max_depth(self, current_depth=0):
        """Get maximum depth of tree"""
        if not self.children:
            return current_depth
        return max(child._get_max_depth(current_depth + 1) for child in self.children)

def generate_descriptions_for_tree(tree_root: TreeNode, project_context: str, project_name: str):
    def get_file_description(node: TreeNode, full_path: str, project_context: str):
        try:
            genai.configure(api_key="AIzaSyDqA_anmBc5of17-j2OOjy1_R6Fv_mwu5Y")
            
            file_extension = pathlib.Path(node.value).suffix
            is_directory = not node.is_file
            
            prompt = f"""
            Analyze this file/folder in a software project:
            
            File/Folder: {node.value}
            Full Path: {full_path}
            Type: {'Directory' if is_directory else 'File'}
            Extension: {file_extension if file_extension else 'N/A'}
            
            Folder structure: {project_context}
            
            Parent Directory: {'/'.join(full_path.split('/')[:-1])}
            
            Please provide a concise description (1-2 sentences) of what this file/folder should contain or do based on:
            1. Its name and location in the project structure
            2. Common software development patterns
            3. File extension and naming conventions

            Or if needed to make it brief, please provide a brief description of the file/folder, focusing on its purpose and expected content.
            If the file is a configuration or script file, include its expected role in the project.
            
            Focus on the purpose and responsibility, not implementation details.
            """
            
            response = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
                contents=prompt
            )
            return response.text
            
        except Exception as e:
            print(f"Error generating description for {node.value}: {e}")
            return f"Auto-generated description for {node.value}"
    
    def traverse_and_describe(node: TreeNode, current_path: str = ""):
        full_path = f"{current_path}/{node.value}" if current_path else node.value
        
        if node.value != project_name and node.is_file:
            print(f"Generating description for: {full_path}")
            description = get_file_description(node, full_path, project_context)
            node.set_description(description)
            node.file_path = full_path
        
        for child in node.children:
            traverse_and_describe(child, full_path)
    
    traverse_and_describe(tree_root)
    return tree_root

def generate_tree(resp: str, project_name: str = "root") -> TreeNode:
    content = resp.strip().replace('```', '')
    lines = content.split('\n')
    stack = []
    root = TreeNode(project_name)
    
    for line in lines:
        if not line.strip():
            continue
        
        indent = 0
        temp_line = line
        while temp_line.startswith('│ ') or temp_line.startswith(' ') or temp_line.startswith('│ ') or temp_line.startswith(' '):
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

def tree_to_graphviz_with_descriptions(node, graph=None, parent_id=None):
    if graph is None:
        graph = graphviz.Digraph(comment='File Tree with Descriptions')
        graph.attr(rankdir='TB')
        graph.attr('node', fontsize='10')
    
    node_id = str(id(node))
    
    label = node.value
    if node.description:
        desc_short = node.description[:50] + "..." if len(node.description) > 50 else node.description
        label += f"\\n({desc_short})"
    
    if node.is_file:
        graph.node(node_id, label, shape='box', style='filled', 
                  fillcolor='lightblue', tooltip=node.description)
    else:
        graph.node(node_id, label, shape='folder', style='filled', 
                  fillcolor='lightgreen', tooltip=node.description)
    
    if parent_id:
        graph.edge(parent_id, node_id)
    
    for child in node.children:
        tree_to_graphviz_with_descriptions(child, graph, node_id)
    
    return graph

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

def get_project_context():
    context_files = ["requirements.md", "README.md", "project_spec.md"]
    context = ""
    
    for file_name in context_files:
        path = pathlib.Path(os.getcwd()) / "docs" / file_name
        if path.exists():
            with open(path, "r") as f:
                content = f.read()
                lines = content.split('\n')[:10]
                context += f"From {file_name}: {' '.join(lines)}\n"
    
    return context

def save_tree_with_descriptions(tree: TreeNode, project_name: str):
    path = pathlib.Path(os.getcwd()) / "docs" / f"{project_name}_tree_with_descriptions.md"
    
    with open(path, "w") as f:
        f.write(f"# File System Tree for {project_name}\n\n")
        f.write("## Structure with Descriptions\n\n")
        
        def write_node(node: TreeNode, level: int = 0):
            indent = "  " * level
            if level == 0:
                f.write(f"{node.value}\n")
            else:
                f.write(f"{indent}- **{node.value}**\n")
            
            if node.description:
                f.write(f"{indent}  - *Description: {node.description}*\n")
            
            for child in node.children:
                write_node(child, level + 1)
        
        write_node(tree)
    
    print(f"Tree with descriptions saved to: {path}")

def generate_fs(project_name : str, add_descriptions: bool = True):
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
    #         project_name = content1.split('\n').strip()
    # else:
    #     print("Requirements file not found at:", path1)
    #     project_name = "root"
    
    #this was useless, i will just use the project name from the ts file
    
    print("Generating file system tree from content...")
    tree = generate_tree(content, project_name=project_name)
    
    if add_descriptions:
        print("Getting project context...")
        project_context = get_project_context()
        print("Generating AI descriptions for tree nodes...")
        tree = generate_descriptions_for_tree(tree, project_context=content, project_name=project_name)
        
        save_tree_with_descriptions(tree, project_name)
    
    print("File system tree generated successfully.")
    
    path = pathlib.Path(os.getcwd()) / "docs" / "folder_structure_tree.md"
    
    # path.parent.mkdir(parents=True, exist_ok=True)
    # with open(path, "w") as f:
    #     f.write(f"# File System Tree for {project_name}\n\n")
    #     tree.print_tree()
    #     print("File system tree saved to:", path)
    
    # print("Tree structure:")
    # tree.print_tree()
    
    # print("DFS Traversal:")
    # tree.dfsTraverse()
    
    # print("Creating visual representation...")
    # if add_descriptions:
    #     graph = tree_to_graphviz_with_descriptions(tree)
    # else:
    #     graph = tree_to_graphviz(tree)
    
    # graph.render(f'docs/{project_name}_tree_visual', format='png', cleanup=True)
    
    return tree

def dfs_populate_Tree_with_code(tree: TreeNode):
    def traverse_and_populate(node: TreeNode):
        if node.is_file and node.file_path:
            try:
                with open(node.file_path, "r", encoding='utf-8') as f:
                    node.code = f.read()
            except Exception as e:
                print(f"Error reading file {node.file_path}: {e}")
                node.code = ""
        
        for child in node.children:
            traverse_and_populate(child)
    
    traverse_and_populate(tree)
    return tree