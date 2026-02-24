from google.genai import types
import re
import json
import os
import time
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

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
        self.error_traces = []
    def add_child(self, child_node):
        self.children.append(child_node)
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
    skip_names = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "ci.yml", "di.yml", "README.md", "README.txt", "README", "LICENSE"}
    # Skip dependency files during initial generation
    if filename in skip_names or filename in DEPENDENCY_FILES_TO_SKIP:
        return False
    return ext in GENERATABLE_FILES or filename in GENERATABLE_FILENAMES


class FileGenerationResult(BaseModel):
    file_content: str = Field(description="The exact content to be written to the file")
    metadata_description: str = Field(description="A 1-2 sentence description of what the file does")


def generate_file(context, filepath, refined_prompt, tree, file_output_format, pm, provider_name: Optional[str] = None) -> Optional[FileGenerationResult]:
    provider_name = provider_name or InferenceManager.get_default_provider()
    provider = InferenceManager.create_provider(provider_name)
    system_instruction = pm.render_file_generation(
        filepath=filepath,
        context=context,
        refined_prompt=refined_prompt,
        tree=tree,
        file_output_format=file_output_format
    )

    result = None

    if provider_name == "google":
        from google.genai import types
        from .utils.inference import retry_api_call
        client = provider.get_client()
        response = retry_api_call(
            client.models.generate_content,
            model=provider.model,
            contents="Generate the file content and metadata description.",
            config=types.GenerateContentConfig(
                systemInstruction=system_instruction,
                response_mime_type="application/json",
                response_schema=FileGenerationResult,
            )
        )
        if response and response.text:
            try:
                data = json.loads(response.text)
                result = FileGenerationResult(**data)
            except (json.JSONDecodeError, ValueError):
                pass
            
    else:
        # OpenRouter/OpenAI via structured outputs
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": "Generate the file content and metadata description."}
        ]
        
        try:
            client = provider.get_client()
            completion = client.beta.chat.completions.parse(
                model=provider.model,
                messages=messages,
                response_format=FileGenerationResult,
            )
            result = completion.choices[0].message.parsed
        except Exception as e:
            try:
                # Need standard chat completion to get the raw string
                completion = client.chat.completions.create(
                    model=provider.model,
                    messages=messages,
                )
                raw_content = completion.choices[0].message.content
                json_str = None
                
                # Strip markdown blocks
                import re
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
                if match:
                    json_str = match.group(1)
                else:
                    # Generic scraping
                    start_idx = raw_content.find('{')
                    if start_idx != -1:
                        depth = 0
                        for i in range(start_idx, len(raw_content)):
                            if raw_content[i] == '{':
                                depth += 1
                            elif raw_content[i] == '}':
                                depth -= 1
                                if depth == 0:
                                    json_str = raw_content[start_idx:i+1]
                                    break
                if json_str:
                    data = json.loads(json_str)
                    result = FileGenerationResult(**data)
            except Exception as fallback_err:
                print(f"Error calling structured output API for file generation: {e}. Fallback failed: {fallback_err}")
                
    if result:
        result.file_content = clean_agent_output(result.file_content)
        
    return result


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
    root_value = root.value if root else project_name

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
            result = generate_file(
                context=context,
                filepath=full_path,
                refined_prompt=refined_prompt,
                tree=tree_structure,
                file_output_format=file_output_format,
                pm=pm,
                provider_name=provider_name
            )

            if not result:
                return None

            content = result.file_content
            metadata = result.metadata_description

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


class ProjectBlueprint(BaseModel):
    software_blueprint_details: Dict[str, Any] = Field(description="Dictionary containing core project intelligence, overview, and features")
    folder_structure: str = Field(description="Raw ASCII string representing the exact directory and file structure tree")
    file_formats: Dict[str, Any] = Field(description="Dictionary mapping precise filepaths from the folder structure to instructions on how each file must be generated")

def generate_project_blueprint(prompt: str, pm, provider_name: Optional[str] = None) -> Optional[ProjectBlueprint]:
    provider_name = provider_name or InferenceManager.get_default_provider()
    provider = InferenceManager.create_provider(provider_name)
    system_info = get_system_info()
    system_instruction = pm.render_project_blueprint(user_prompt=prompt, system_info=system_info)
    
    if provider_name == "google":
        from google.genai import types
        from .utils.inference import retry_api_call
        client = provider.get_client()
        response = retry_api_call(
            client.models.generate_content,
            model=provider.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                systemInstruction=system_instruction,
                response_mime_type="application/json",
                response_schema=ProjectBlueprint,
            )
        )
        if not response or not response.text:
            return None
            
        try:
            data = json.loads(response.text)
            return ProjectBlueprint(**data)
        except (json.JSONDecodeError, ValueError):
            return None
            
    else:
        # OpenRouter/OpenAI via structured outputs
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]
        
        try:
            client = provider.get_client()
            completion = client.beta.chat.completions.parse(
                model=provider.model,
                messages=messages,
                response_format=ProjectBlueprint,
            )
            return completion.choices[0].message.parsed
        except Exception as e:
            # Fallback for providers that don't fully support structured outputs
            # and may return stringified JSON with markdown ticks instead
            try:
                # Need standard chat completion to get the raw string
                completion = client.chat.completions.create(
                    model=provider.model,
                    messages=messages,
                )
                raw_content = completion.choices[0].message.content
                json_str = None
                import re
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
                if match:
                    json_str = match.group(1)
                else:
                    start_idx = raw_content.find('{')
                    if start_idx != -1:
                        depth = 0
                        for i in range(start_idx, len(raw_content)):
                            if raw_content[i] == '{':
                                depth += 1
                            elif raw_content[i] == '}':
                                depth -= 1
                                if depth == 0:
                                    json_str = raw_content[start_idx:i+1]
                                    break
                if json_str:
                    data = json.loads(json_str)
                    return ProjectBlueprint(**data)
            except Exception as fallback_err:
                print(f"Error calling structured output API: {e}. Fallback failed: {fallback_err}")
                
            return None


def generate_tree(resp, project_name="root"):
    content = resp.strip().replace('```', '').strip()
    lines = content.split('\n')
    tree_line_pattern = re.compile(r'^(?:[│|]\s*)*(?:├──\s*|└──\s*|\|--\s*|\+--\s*|`--\s*|\|___\s*)?([^│├└|+#\n]+?)(?:/)?(?:\s*#.*)?$', re.IGNORECASE)

    root = None
    root_name = None
    root_line_index = -1

    for i, line in enumerate(lines):
        if not line.strip():
            continue

        match = tree_line_pattern.match(line.strip())
        if match:
            raw_name = match.group(1)
            root_name = re.sub(r'^[│├└─|`+\-\s]+', '', raw_name).strip().rstrip('/')
        else:
            root_name = line.strip()
            if '#' in root_name:
                root_name = root_name.split('#')[0].strip()
            root_name = re.sub(r'^[│├└─|`+\-\s]+', '', root_name).strip().rstrip('/')

        # Replace spaces with underscores in folder names
        if root_name:
            root_name = root_name.replace(' ', '_')
            root = TreeNode(root_name)
            root_line_index = i
            break

    if not root:
        root = TreeNode(project_name)
        root_line_index = -1

    stack = [root]

    for i, line in enumerate(lines):
        if not line.strip() or i <= root_line_index:
            continue

        indent = 0
        temp_line = line
        while True:
            if temp_line.startswith('│   ') or temp_line.startswith('|   ') or temp_line.startswith('    '):
                temp_line = temp_line[4:]
                indent += 1
            elif temp_line.startswith('│ ') or temp_line.startswith('| '):
                temp_line = temp_line[2:]
                indent += 1
            elif temp_line.startswith('\t'):
                temp_line = temp_line[1:]
                indent += 1
            else:
                break

        match = tree_line_pattern.match(line.strip())
        if not match:
            name = line.strip()
            if '#' in name:
                name = name.split('#')[0].strip()
            name = re.sub(r'^[│├└─|`+\-\s]+', '', name).strip()
        else:
            raw_name = match.group(1)
            name = re.sub(r'^[│├└─|`+\-\s]+', '', raw_name).strip()

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
    from .utils.dependencies import DependencyAnalyzer
    from .docker.testing import run_docker_testing
    from .docker.generator import DockerTestFileGenerator
    from .utils.error_tracker import ErrorTracker

    def emit(event_type, message, **kwargs):
        if on_status:
            on_status(event_type, message, **kwargs)

    pm = PromptManager()

    provider_name = provider_name or InferenceManager.get_default_provider()

    emit("step", "Analyzing structure and creating unified project blueprint...")
    blueprint = generate_project_blueprint(user_prompt, pm, provider_name)
    
    if not blueprint:
        emit("error", "Failed to generate project blueprint.")
        return None

    software_blueprint = blueprint.software_blueprint_details
    folder_struc = blueprint.folder_structure
    file_format = blueprint.file_formats
    file_output_format = file_format

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
            on_status=on_status,
            provider=InferenceManager.create_provider(provider_name)
        )

        test_gen_results = test_gen.generate_all()
    except Exception:
        pass

    emit("step", "Starting dependency analysis for entire project...")
    dependency_analyzer.analyze_project_files(project_root_path, folder_tree=folder_tree, folder_structure=folder_struc)

    from .utils.dependencies import build_dependency_graph_tree
    dep_graph = build_dependency_graph_tree(project_root_path, dependency_analyzer)
    print("\n[dependency_graph]\n" + dep_graph + "\n")

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

    # Dependency resolution disabled for ablation study
    emit("step", "Skipping dependency resolution (disabled)...")
    error_tracker = ErrorTracker(project_root_path, folder_tree)
    dep_results = {"success": True, "iterations": 0, "remaining_errors": [], "skipped": True}

    emit("step", "Running Docker testing pipeline...")

    docker_results = run_docker_testing(
        project_root=project_root_path,
        software_blueprint=software_blueprint,
        folder_structure=folder_struc,
        file_output_format=file_output_format,
        pm=pm,
        error_tracker=error_tracker,
        dependency_analyzer=dependency_analyzer,
        on_status=on_status,
        provider_name=provider_name,
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

