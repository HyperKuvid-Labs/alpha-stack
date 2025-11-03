from google import genai
from google.genai import types
from dotenv import load_dotenv
import re
import json
import os
from folder_tree import TreeNode, DependencyAnalyzer
from prompt_manager import PromptManager
from genai_client import get_client
from dfs_tree_gen import dfs_tree_and_gen
from dfs_feedback import run_feedback_loop
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
load_dotenv(dotenv_path='.env')
import matplotlib.pyplot as plt
import networkx as nx


def inital_software_blueprint(prompt: str, pm: PromptManager) -> str:
    """
    Generates the high level software blueprint with title, roles and features
    
    Args:
        prompt: User's project description
        pm: PromptManager instance for rendering templates
    
    Returns:
        Parsed JSON dictionary with project blueprint
    """
    client = get_client()
    system_instruction = pm.render_software_blueprint(user_prompt=prompt)
    
    chat = client.chats.create(
        model='gemini-2.5-pro',
        config=types.GenerateContentConfig(systemInstruction=system_instruction)
    )
    
    response = chat.send_message(prompt)
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    
    if match:
        clean_json_str = match.group(0)
        try:
            data = json.loads(clean_json_str)
            print("✅ Successfully parsed blueprint!")
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
            
            print("🛠️  Tech Stack:")
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


def folder_structure(project_overview: str, pm: PromptManager):
    """
    Generates the folder structure for the project description
    
    Args:
        project_overview: The project blueprint dictionary
        pm: PromptManager instance for rendering templates
    
    Returns:
        String representation of folder structure
    """
    client = get_client()
    system_instruction = pm.render_folder_structure(project_overview=project_overview)
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=types.Content(
            role='user',
            parts=[types.Part.from_text(text=json.dumps(project_overview))]
        ),
        config=types.GenerateContentConfig(systemInstruction=system_instruction)
    )
    return response.text


def files_format(project_overview: str, folder_structure: str, pm: PromptManager):
    """
    Generates the JSON file format contracts
    
    Args:
        project_overview: The project blueprint dictionary
        folder_structure: String representation of folder structure
        pm: PromptManager instance for rendering templates
    
    Returns:
        JSON string with file contracts
    """
    client = get_client()
    system_instruction = pm.render_file_format(
        project_overview=project_overview,
        folder_structure=folder_structure
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=types.Content(
            role='user',
            parts=[
                types.Part.from_text(text=json.dumps(project_overview)),
                types.Part.from_text(text=json.dumps(folder_structure))
            ]
        ),
        config=types.GenerateContentConfig(systemInstruction=system_instruction)
    )
    return response.text
def generate_tree(resp: str, project_name: str = "root") -> TreeNode:
    import re
    
    content = resp.strip().replace('```', '').strip()
    lines = content.split('\n')
    tree_line_pattern = re.compile(r'^(?:│\s*)*(?:├──\s*|└──\s*)?([^│├└#\n]+?)(?:/)?(?:\s*#.*)?$', re.IGNORECASE)
    
    root = None
    root_name = None
    root_line_index = -1
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        
        match = tree_line_pattern.match(line.strip())
        if match:
            root_name = match.group(1).strip().rstrip('/')
        else:
            root_name = line.strip()
            if '#' in root_name:
                root_name = root_name.split('#')[0].strip()
            root_name = re.sub(r'[│├└─\s]+', '', root_name).strip().rstrip('/')
        
        if root_name:
            root = TreeNode(root_name)
            root_line_index = i
            break
    
    if not root:
        root = TreeNode("root")
        root_line_index = -1
    
    stack = [root]

    for i, line in enumerate(lines):
        if not line.strip() or i <= root_line_index:
            continue

        indent = 0
        temp_line = line
        while temp_line.startswith('│   ') or temp_line.startswith('    ') or temp_line.startswith('│ ') or temp_line.startswith('    '):
            temp_line = temp_line[4:]
            indent += 1

        match = tree_line_pattern.match(line.strip())
        if not match:
            name = line.strip()
            if '#' in name:
                name = name.split('#')[0].strip()
            name = re.sub(r'[│├└─\s]+', '', name).strip()
        else:
            name = match.group(1).strip()
        
        name = name.rstrip('/')
        
        if not name:
            continue

        node = TreeNode(name)

        if indent == 0:
            root.add_child(node)
            stack = [root, node]
        else:
            while len(stack) <= indent:
                stack.append(root)
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
    Executes the main logic with Jinja2-based prompting
    """
    print("=" * 80)
    print("🚀 Starting Backend Process")
    print("=" * 80)
    
    pm = PromptManager(templates_dir="prompts")
    print("✅ PromptManager initialized with templates from 'prompts/' directory\n")
    
    user_prompt = """A simple terminal-based calculator using Python. When you run it, it asks for two numbers and an operation (addition, subtraction, or multiplication). It performs the calculation and displays the result. That's it - very simple, no frontend, just command line interface."""
    
    print("📋 Step 1: Generating software blueprint...")
    software_blueprint = inital_software_blueprint(user_prompt, pm)
    
    print("\n📁 Step 2: Generating folder structure...")
    folder_struc = folder_structure(software_blueprint, pm)
    print(folder_struc)
    
    print("\n📄 Step 3: Generating file format contracts...")
    file_format = files_format(software_blueprint, folder_struc, pm)
    print(file_format)
    
    print("\n🌳 Step 4: Building project tree and generating files...")
    folder_tree = generate_tree(folder_struc, project_name="")
    dependency_analyzer = DependencyAnalyzer()
    
    output_base_dir = "/Users/adityagk/Desktop/project-1/created_projects"
    os.makedirs(output_base_dir, exist_ok=True)
    
    json_file_name = os.path.join(output_base_dir, "projects_metadata.json")
    metadata_dict = {}
    start_time = time.time()
    
    lock = Lock()
    
    with ThreadPoolExecutor() as executor:
        dfs_tree_and_gen(
            root=folder_tree,
            refined_prompt=software_blueprint,
            tree_structure=folder_struc,
            project_name="",
            current_path="",
            parent_context="",
            json_file_name=json_file_name,
            metadata_dict=metadata_dict,
            dependency_analyzer=dependency_analyzer,
            file_output_format=file_format,
            output_base_dir=output_base_dir,
            pm=pm
        )
    
    print("\n📊 Step 5: Visualizing dependency graph...")
    dependency_analyzer.visualize_graph()
    
    print("\n🔗 Step 6: Updating metadata with dependencies...")
    project_files = list(metadata_dict.keys())
    for file_path, entries in metadata_dict.items():
        deps = dependency_analyzer.get_dependencies(file_path)
        for entry in entries:
            entry["couples_with"] = deps
    
    with open(json_file_name, 'w') as f:
        json.dump(metadata_dict, f, indent=4)
    
    print("\n🔄 Step 7: Running feedback loop (dependency resolution + Docker testing)...")
    project_root_path = os.path.join(output_base_dir, folder_tree.value)
    
    if os.path.exists(project_root_path):
        print("🔍 Refreshing dependencies to resolve internal imports...")
        dependency_analyzer._refresh_existing_dependencies()
        
        try:
            if isinstance(software_blueprint, str):
                software_blueprint = json.loads(software_blueprint)
        except:
            pass
        
        try:
            if isinstance(file_format, str):
                file_output_format = json.loads(file_format)
            else:
                file_output_format = file_format
        except:
            file_output_format = {}
        
        feedback_result = run_feedback_loop(
            project_root=project_root_path,
            dependency_analyzer=dependency_analyzer,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            pm=pm
        )
        
        dep_result = feedback_result.get("dependency_resolution", {})
        docker_result = feedback_result.get("docker_testing", {})
        
        if dep_result.get("success"):
            print(f"\n✅ Dependency resolution completed successfully!")
            print(f"   Iterations: {dep_result.get('iterations', 0)}")
        else:
            print(f"\n⚠️  Dependency resolution completed with remaining issues")
            print(f"   Iterations: {dep_result.get('iterations', 0)}")
            remaining_errors = dep_result.get("remaining_errors", [])
            if remaining_errors:
                print(f"   Remaining errors: {len(remaining_errors)}")
                for error in remaining_errors[:5]:
                    print(f"     - {error.get('file', 'unknown')}: {error.get('message', 'unknown error')}")
        
        if docker_result.get("success"):
            print(f"\n✅ Docker testing completed successfully!")
            print(f"   Iterations: {docker_result.get('iterations', 0)}")
        else:
            print(f"\n⚠️  Docker testing completed with remaining issues")
            print(f"   Iterations: {docker_result.get('iterations', 0)}")
            remaining_errors = docker_result.get("remaining_errors", [])
            if remaining_errors:
                print(f"   Remaining errors: {len(remaining_errors)}")
                for error in remaining_errors[:5]:
                    print(f"     - {error.get('error', 'unknown error')}")
    else:
        print(f"\n⚠️  Project root not found at {project_root_path}, skipping feedback loop")
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print("\n" + "=" * 80)
    print(f"✅ Completed in {elapsed:.2f} seconds")
    print("=" * 80)
    
    print("\n📝 Summary:")
    print(f"  - Project root: {folder_tree.value}")
    print(f"  - Output directory: {output_base_dir}")
    print(f"  - Files generated: {len(project_files)}")
    print(f"  - Metadata saved to: {json_file_name}")
    print(f"  - Dependency graph visualized")
    if os.path.exists(project_root_path):
        print(f"  - Dependency resolution executed")
        print(f"  - Docker testing pipeline executed")
if __name__ == '__main__':   
    main()