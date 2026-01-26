from google.genai import types
import re
import json
import os
import time
from typing import Optional
from .utils.helpers import get_system_info, clean_agent_output, GENERATABLE_FILES, GENERATABLE_FILENAMES
from .utils.inference import InferenceManager
from .utils.prompt_manager import PromptManager
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Lock
from queue import Queue, Empty



class TreeNode:
    def __init__(self, value):
        self.value = value
        self.children = []
        self.is_file = False

    def add_child(self, child_node):
        self.children.append(child_node)


# Dependency files that should be skipped during initial generation
DEPENDENCY_FILES_TO_SKIP = {
    'requirements.txt', 'requirements-dev.txt', 'requirements-test.txt',
    'Pipfile', 'Pipfile.lock', 'pyproject.toml', 'poetry.lock', 'setup.py', 'setup.cfg',
    'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'bun.lockb',
    'go.mod', 'go.sum',
    'Cargo.toml', 'Cargo.lock',
    'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'gradle.properties',
    'composer.json', 'composer.lock',
    'Gemfile', 'Gemfile.lock',
    'mix.exs', 'mix.lock',
    'pubspec.yaml', 'pubspec.lock',
    'CMakeLists.txt', 'conanfile.txt', 'vcpkg.json',
    'rebar.config', 'rebar.lock',
}

def should_generate_content(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    skip_names = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "ci.yml", "di.yml"}
    # Skip dependency files during initial generation
    if filename in skip_names or filename in DEPENDENCY_FILES_TO_SKIP:
        return False
    return ext in GENERATABLE_FILES or filename in GENERATABLE_FILENAMES


def generate_file_metadata(context, filepath, refined_prompt, tree, json_file_name, file_content, file_output_format, pm, provider_name: Optional[str] = None):
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)
    prompt = pm.render_file_metadata(
        filename=filename,
        file_type=file_type,
        context=context,
        refined_prompt=refined_prompt,
        tree=tree,
        file_content=file_content,
        file_output_format=file_output_format
    )
    
    provider_name = provider_name or InferenceManager.get_default_provider()
    provider = InferenceManager.create_provider(provider_name)
    
    messages = [{"role": "user", "content": prompt}]
    response = provider.call_model(messages)
    
    return provider.extract_text(response)


def generate_file_content(context, filepath, refined_prompt, tree, json_file_name, file_output_format, pm, provider_name: Optional[str] = None):
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)
    prompt = pm.render_file_content(
        filename=filename,
        file_type=file_type,
        context=context,
        refined_prompt=refined_prompt,
        tree=tree,
        file_output_format=file_output_format
    )
    
    provider_name = provider_name or InferenceManager.get_default_provider()
    provider = InferenceManager.create_provider(provider_name)
    
    messages = [{"role": "user", "content": prompt}]
    response = provider.call_model(messages)
    response_text = provider.extract_text(response)
    cleaned_output = clean_agent_output(response_text)
    return cleaned_output


def dfs_tree_and_gen(root, refined_prompt, tree_structure, project_name, current_path="",
                     parent_context="", json_file_name="", metadata_dict=None, 
                     dependency_analyzer=None, file_output_format="", max_workers=20,
                     output_base_dir="", pm=None, on_status=None, provider_name: Optional[str] = None):
    if metadata_dict is None:
        metadata_dict = {}
    
    if pm is None:
        # If running as installed package, prompts might not be in CWD
        # We rely on PromptManager's internal logic to find them now
        pm = PromptManager()
    
    lock = Lock()
    work_queue = Queue()
    root_value = root.value if root else "root"
    
    if output_base_dir:
        root_full_path = os.path.join(output_base_dir, root_value)
    else:
        root_full_path = root_value
    
    if not os.path.exists(root_full_path):
        os.makedirs(root_full_path, exist_ok=True)
    
    for child in root.children:
        work_queue.put({
            'node': child,
            'current_path': root_value,
            'parent_context': parent_context,
            'is_top_level': False,
            'output_base_dir': output_base_dir,
            'root_value': root_value
        })
    
    def process_work_item(work_item):
        node = work_item['node']
        current_path = work_item['current_path']
        parent_context = work_item['parent_context']
        work_output_base_dir = work_item.get('output_base_dir', output_base_dir)
        root_val = work_item.get('root_value', root.value if root else "root")
        
        clean_name = node.value.split('#')[0].strip()
        clean_name = clean_name.replace('(', '').replace(')', '')
        clean_name = clean_name.replace('uploads will go here, e.g., ', '')

        relative_path = os.path.join(current_path, clean_name) if current_path else clean_name
        
        if work_output_base_dir:
            full_path = os.path.join(work_output_base_dir, relative_path)
        else:
            full_path = relative_path

        context = os.path.join(parent_context, clean_name) if parent_context else clean_name

        if node.is_file:
            return process_file(
                node, full_path, context, refined_prompt, tree_structure,
                json_file_name, file_output_format, metadata_dict,
                dependency_analyzer, lock, pm, on_status, provider_name
            )
        else:
            return process_directory(node, full_path, context, work_queue, work_output_base_dir, lock, root_val, on_status)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        active_futures = set()
        
        while True:
            while len(active_futures) < max_workers:
                try:
                    work_item = work_queue.get_nowait()
                    future = executor.submit(process_work_item, work_item)
                    active_futures.add(future)
                except Empty:
                    break
            
            if not active_futures:
                try:
                    work_item = work_queue.get_nowait()
                    future = executor.submit(process_work_item, work_item)
                    active_futures.add(future)
                    continue
                except Empty:
                    break
            
            if active_futures:
                done, not_done = wait(active_futures, timeout=1, return_when=FIRST_COMPLETED)
                for future in done:
                    try:
                        result = future.result()
                        if result and 'children' in result:
                            for child_work in result['children']:
                                work_queue.put(child_work)
                    except Exception:
                        pass
                active_futures = set(not_done)


def process_file(node, full_path, context, refined_prompt, tree_structure,
                json_file_name, file_output_format, metadata_dict,
                dependency_analyzer, lock, pm, on_status=None, provider_name: Optional[str] = None):
    try:
        parent_dir = os.path.dirname(full_path)
        if parent_dir:
            with lock:
                if not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)

        if should_generate_content(full_path):
            content = generate_file_content(
                context=context,
                filepath=full_path,
                refined_prompt=refined_prompt,
                tree=tree_structure,
                json_file_name=json_file_name,
                file_output_format=file_output_format,
                pm=pm,
                provider_name=provider_name
            )
            
            metadata = generate_file_metadata(
                context=context,
                filepath=full_path,
                refined_prompt=refined_prompt,
                tree=tree_structure,
                json_file_name=json_file_name,
                file_content=content,
                file_output_format=file_output_format,
                pm=pm,
                provider_name=provider_name
            )
            
            with lock:
                with open(full_path, 'w') as f:
                    f.write(content)
                
                if full_path not in metadata_dict:
                    metadata_dict[full_path] = []
                metadata_dict[full_path].append({
                    "description": metadata
                })
            
    except Exception:
        pass
    
    return None


def process_directory(node, full_path, context, work_queue, output_base_dir="", lock=None, root_value="", on_status=None):
    try:
        if lock:
            with lock:
                if not os.path.exists(full_path):
                    os.makedirs(full_path, exist_ok=True)
        else:
            os.makedirs(full_path, exist_ok=True)
        
        if output_base_dir:
            rel_path = os.path.relpath(full_path, output_base_dir)
        else:
            rel_path = full_path
        
        children_work = []
        for child in node.children:
            child_work = {
                'node': child,
                'current_path': rel_path,
                'parent_context': context,
                'is_top_level': False,
                'output_base_dir': output_base_dir,
                'root_value': root_value
            }
            children_work.append(child_work)
        
        return {'children': children_work}
        
    except OSError:
        return None


def initial_software_blueprint(prompt, pm, provider_name: Optional[str] = None):
    provider_name = provider_name or InferenceManager.get_default_provider()
    provider = InferenceManager.create_provider(provider_name)
    system_instruction = pm.render_software_blueprint(user_prompt=prompt)
    
    if provider_name == "google":
        # Use Google's chat API for system instructions
        from google.genai import types
        from .utils.inference import retry_api_call
        client = provider.get_client()
        chat_obj = retry_api_call(
            client.chats.create,
            model=provider.model,
            config=types.GenerateContentConfig(systemInstruction=system_instruction)
        )
        response = retry_api_call(chat_obj.send_message, prompt)
        response_text = response.text
    else:
        # For OpenRouter/OpenAI, use system message
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]
        response = provider.call_model(messages)
        response_text = provider.extract_text(response)
    
    match = re.search(r'\{.*\}', response_text, re.DOTALL)
    
    if match:
        clean_json_str = match.group(0)
        try:
            data = json.loads(clean_json_str)
            # Sanitize project name: replace spaces with underscores
            if "projectDetails" in data and "projectName" in data["projectDetails"]:
                data["projectDetails"]["projectName"] = data["projectDetails"]["projectName"].replace(' ', '_')
            system_info = get_system_info()
            data["systemInfo"] = system_info
            return data
        except json.JSONDecodeError:
            return None
    return None


def folder_structure(project_overview, pm, provider_name: Optional[str] = None):
    provider_name = provider_name or InferenceManager.get_default_provider()
    provider = InferenceManager.create_provider(provider_name)
    system_instruction = pm.render_folder_structure(project_overview=project_overview)
    
    if provider_name == "google":
        from google.genai import types
        from .utils.inference import retry_api_call
        client = provider.get_client()
        response = retry_api_call(
            client.models.generate_content,
            model=provider.model,
            contents=types.Content(
                role='user',
                parts=[types.Part.from_text(text=json.dumps(project_overview))]
            ),
            config=types.GenerateContentConfig(systemInstruction=system_instruction)
        )
        return response.text
    else:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": json.dumps(project_overview)}
        ]
        response = provider.call_model(messages)
        return provider.extract_text(response)


def files_format(project_overview, folder_structure, pm, provider_name: Optional[str] = None):
    provider_name = provider_name or InferenceManager.get_default_provider()
    provider = InferenceManager.create_provider(provider_name)
    system_instruction = pm.render_file_format(
        project_overview=project_overview,
        folder_structure=folder_structure
    )
    
    if provider_name == "google":
        from google.genai import types
        from .utils.inference import retry_api_call
        client = provider.get_client()
        response = retry_api_call(
            client.models.generate_content,
            model=provider.model,
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
    else:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": json.dumps({"project_overview": project_overview, "folder_structure": folder_structure})}
        ]
        response = provider.call_model(messages)
        return provider.extract_text(response)


def generate_tree(resp, project_name="root"):
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
        
        # Replace spaces with underscores in folder names
        if root_name:
            root_name = root_name.replace(' ', '_')
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
        
        # Replace spaces with underscores in folder/file names
        name = name.replace(' ', '_')
        
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

    def mark_files_and_dirs(node):
        if not node.children:
            node.is_file = True
        else:
            node.is_file = False
            for child in node.children:
                mark_files_and_dirs(child)

    mark_files_and_dirs(root)
    return root


def generate_project(user_prompt, output_base_dir, on_status=None, provider_name: Optional[str] = None):
    from .utils.dependencies import DependencyAnalyzer, DependencyFeedbackLoop
    from .docker.testing import run_docker_testing
    from .docker.generator import DockerTestFileGenerator
    from .utils.error_tracker import ErrorTracker
    
    def emit(event_type, message, **kwargs):
        if on_status:
            on_status(event_type, message, **kwargs)
    
    pm = PromptManager()
    
    provider_name = provider_name or InferenceManager.get_default_provider()
    
    emit("step", "Creating software blueprint...")
    software_blueprint = initial_software_blueprint(user_prompt, pm, provider_name)
    
    emit("step", "Creating folder structure...")
    folder_struc = folder_structure(software_blueprint, pm, provider_name)
    
    emit("step", "Creating file format contracts...")
    file_format = files_format(software_blueprint, folder_struc, pm, provider_name)
    
    emit("step", "Building project tree and generating files...")
    folder_tree = generate_tree(folder_struc, project_name="")
    dependency_analyzer = DependencyAnalyzer()
    os.makedirs(output_base_dir, exist_ok=True)
    json_file_name = os.path.join(output_base_dir, "projects_metadata.json")
    metadata_dict = {}
    start_time = time.time()
    
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
        pm=pm,
        on_status=on_status,
        provider_name=provider_name
    )
    
    project_root_path = os.path.join(output_base_dir, folder_tree.value)
    
    if not os.path.exists(project_root_path):
        return None
    
    with open(json_file_name, 'w') as f:
        json.dump(metadata_dict, f, indent=4)
    
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
    
    emit("step", "Generating Dockerfile and test files...")
    
    try:
        test_gen = DockerTestFileGenerator(
            project_root=project_root_path,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            metadata_dict=metadata_dict,
            dependency_analyzer=dependency_analyzer,
            pm=pm,
            on_status=on_status
        )
        
        test_gen_results = test_gen.generate_all()
    except Exception:
        pass
    
    emit("step", "Starting dependency analysis for entire project...")
    dependency_analyzer.analyze_project_files(project_root_path, folder_tree=folder_tree, folder_structure=folder_struc)
    
    emit("step", "Extracting external dependencies and generating dependency files...")
    try:
        from .utils.dependency_file_generator import (
            extract_all_external_dependencies,
            DependencyFileGenerator
        )
        
        # Extract all external dependencies from all files in the project
        external_dependencies = extract_all_external_dependencies(dependency_analyzer, project_root_path)
        
        # Generate dependency files using the coding agent
        dep_file_gen = DependencyFileGenerator(
            project_root=project_root_path,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            external_dependencies=external_dependencies,
            pm=pm,
            provider_name=provider_name,
            on_status=on_status
        )
        
        dep_file_results = dep_file_gen.generate_all()
        
        # Re-analyze project files to include the newly generated dependency files
        dependency_analyzer.analyze_project_files(project_root_path, folder_tree=folder_tree, folder_structure=folder_struc)
    except Exception as e:
        print(f"Error generating dependency files: {e}")
    
    emit("step", "Running dependency resolution...")
    
    error_tracker = ErrorTracker(project_root_path)
    feedback_loop = DependencyFeedbackLoop(
        dependency_analyzer=dependency_analyzer,
        project_root=project_root_path,
        software_blueprint=software_blueprint,
        folder_structure=folder_struc,
        file_output_format=file_output_format,
        pm=pm,
        error_tracker=error_tracker
    )
    dep_results = feedback_loop.run_feedback_loop()
    
    emit("step", "Running Docker testing pipeline...")
    
    docker_results = run_docker_testing(
        project_root=project_root_path,
        software_blueprint=software_blueprint,
        folder_structure=folder_struc,
        file_output_format=file_output_format,
        pm=pm,
        error_tracker=error_tracker,
        dependency_analyzer=dependency_analyzer,
        on_status=on_status
    )
    
    for file_path, entries in metadata_dict.items():
        deps = dependency_analyzer.get_dependency_details(file_path)
        for entry in entries:
            entry["couples_with"] = deps
    
    with open(json_file_name, 'w') as f:
        json.dump(metadata_dict, f, indent=4)
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    overall_success = dep_results.get("success", False) and docker_results.get("success", False)
    
    if os.path.exists(json_file_name):
        try:
            os.remove(json_file_name)
        except Exception:
            pass
    
    return {
        "project_path": project_root_path,
        "success": overall_success,
        "dependency_resolution": dep_results,
        "docker_testing": docker_results,
        "elapsed_time": elapsed
    }

