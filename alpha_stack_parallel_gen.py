from google import genai
from google.genai import types
from dotenv import load_dotenv
import re
import json
import os
from folder_tree import TreeNode,DependencyAnalyzer
from prompt import software_blueprint_prompt,folder_structure_prompt,file_format_prompt
from genai_client import get_client
from dfs_tree_gen import dfs_tree_and_gen
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
load_dotenv(dotenv_path='.env')
import matplotlib.pyplot as plt
import networkx as nx

# --- Your Functions (Modified to use get_client()) ---

def inital_software_blueprint(prompt:str)->str:
    "gives the high level software blueprint with title roles and features"
    client = get_client()
    chat=client.chats.create(model='gemini-2.5-pro',config=types.GenerateContentConfig(systemInstruction=software_blueprint_prompt))
    # response = client.models.generate_content(
    # model="gemini-2.5-pro",
    # contents = types.Content(role='user',parts=[types.Part.from_text(text=prompt)]),
    # config=types.GenerateContentConfig(systemInstruction=software_blueprint_prompt)
    # )
    response=chat.send_message(prompt)
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        clean_json_str = match.group(0)
        try:
         data = json.loads(clean_json_str)
         print("avolodhan parsed !!!")
         print("Project Name:", data["projectDetails"]["projectName"], "\n")
         print("🔹 Features:")
         for feature in data.get("features", []):
                print(f"  - {feature['name']}:")
                for desc in feature["description"]:
                    print(f"      • {desc}")
         print()
         print("👥 User Roles:")
         for role in data.get("userRoles", []):
                print(f"  - {role['role']}")
                print(f"      Permissions: {role['permissions']}")
                print(f"      Responsibilities: {role['responsibilities']}")
         print()
         print("Tech Stack:")
         for section, details in data.get("techStack", {}).items():
                print(f"  - {section.capitalize()}:")
                if isinstance(details, dict):
                    for k, v in details.items():
                        print(f"      {k}: {v}")
                else:
                    print(f"      {details}")
         print()
         return data
        except json.JSONDecodeError as e:
            return ("Error decoding JSON:", e)
def folder_structure(project_overveiw:str):
    """generates the folder_structure for the project description"""
    client = get_client()
    response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents = types.Content(role='user',parts=[types.Part.from_text(text=json.dumps(project_overveiw))
    ]),
    config=types.GenerateContentConfig(systemInstruction=folder_structure_prompt)
    )
    return response.text
def files_format(project_overveiw:str,folder_structure:str):
    """generates the json file of each output"""
    client = get_client()
    response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents = types.Content(role='user',parts=[types.Part.from_text(text=json.dumps(project_overveiw))
    ,types.Part.from_text(text=json.dumps(folder_structure))]),
    config=types.GenerateContentConfig(systemInstruction=file_format_prompt)
    )
    return response.text
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
def main():
    """
    Executes the main logic and returns the features and folder structure.
    """
    print("--- Starting Backend Process ---")
    user_prompt="""A tiny app where a user can add, view, and delete short text notes."""
    software_blueprint = inital_software_blueprint(user_prompt)
    folder_struc = folder_structure(software_blueprint)
    print(folder_struc)
    file_format=files_format(software_blueprint,folder_struc)
    print(file_format)
    project_name=software_blueprint["projectDetails"]["projectName"]
    folder_tree=generate_tree(folder_struc,project_name)
    dependency_analyzer=DependencyAnalyzer()
    json_file_name = "projects_metadata.json"
    metadata_dict = {}
    output_dir = os.path.dirname(json_file_name)
    start_time=time.time()
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    lock = Lock()
    with ThreadPoolExecutor() as executor :
        dfs_tree_and_gen(root=folder_tree, refined_prompt=software_blueprint, tree_structure=folder_struc, project_name=project_name, current_path="", parent_context="", json_file_name=json_file_name, metadata_dict=metadata_dict, dependency_analyzer=dependency_analyzer,file_output_format=file_format,executor=executor, lock=lock)
    dependency_analyzer.visualize_graph()
    for file_path, entries in metadata_dict.items():
        deps = dependency_analyzer.get_dependencies(file_path)
        for entry in entries:
            entry["couples_with"] = deps
    with open(json_file_name, 'w') as f:
        json.dump(metadata_dict, f, indent=4)
        end_time = time.time()
    elapsed = end_time - start_time
    print(f"\nCompleted in {elapsed:.2f} seconds")
    print("Running final validation pass...")
if __name__ == '__main__':   
    main()