from determine_tech_stack import gen_and_store_ts
from rgen_fs import generate_structure
from tree_thing import generate_fs, dfs_populate_Tree_with_code
from generatable_files import get_generatable_files
from dfs_tree_and_gen import dfs_tree_and_gen
from dependency_analyzer import DependencyAnalyzer
import pathlib
import os

prompt = "I want to build a python app that can handle files and folders using rust and python, with a focus on performance and scalability. The app should be able to process large datasets efficiently and provide a user-friendly interface. Give it an indian name."
project_name = gen_and_store_ts(prompt)
print("Project Name:", project_name)
generate_structure()
tree = generate_fs(project_name=project_name)
# print("="*60)
# print("ENHANCED TREE ANALYSIS")
# print("="*60)

# tree.dfs_traverse_debug()

# total_files = tree._count_files()

get_generatable_files()
path = pathlib.Path(os.getcwd()) / "docs" / "tech_stack_reqs.md"
with open(path, "r") as f:
    project_desc = f.read()
pr = pathlib.Path(os.getcwd()) / "docs" / "folder_structure.md"
if not pr.exists():
    print("Folder structure documentation not found at:", pr)
    pr = None
if pr:
    with open(pr, "r") as f:
        folder_structure = f.read()

dependency_analyzer = DependencyAnalyzer()
dfs_tree_and_gen(tree, project_desc=project_desc, project_name=project_name, parent_context="", current_path="", is_top_level=True, folder_structure=folder_structure, dependency_analyzer=dependency_analyzer)
# dependency_analyzer.visualize_graph()
print("Populating the nodes of the tree with the code")
dfs_populate_Tree_with_code(tree)



