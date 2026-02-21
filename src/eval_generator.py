from google.genai import types
import re
import json
import os
import time
from typing import Optional
from utils.helpers import (
    get_system_info,
    clean_agent_output,
    GENERATABLE_FILES,
    GENERATABLE_FILENAMES,
)
from utils.inference import InferenceManager
from utils.prompt_manager import PromptManager
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Lock
from queue import Queue, Empty
from jinja2 import Environment, FileSystemLoader

class TreeNode:
    def __init__(self, value):
        self.value = value
        self.children = []
        self.is_file = False

    def add_child(self, child_node):
        self.children.append(child_node)
DEPENDENCY_FILES_TO_SKIP = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "Pipfile",
    "Pipfile.lock",
    "pyproject.toml",
    "poetry.lock",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "gradle.properties",
    "composer.json",
    "composer.lock",
    "Gemfile",
    "Gemfile.lock",
    "mix.exs",
    "mix.lock",
    "pubspec.yaml",
    "pubspec.lock",
    "CMakeLists.txt",
    "conanfile.txt",
    "vcpkg.json",
    "rebar.config",
    "rebar.lock",
}

def should_generate_content(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    skip_names = {
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "ci.yml",
        "di.yml",
        "README.md",
    }
    if filename in skip_names or filename in DEPENDENCY_FILES_TO_SKIP:
        return False
    return ext in GENERATABLE_FILES or filename in GENERATABLE_FILENAMES


def generate_file_metadata(
    context,
    filepath,
    refined_prompt,
    tree,
    json_file_name,
    file_content,
    file_output_format,
    pm,
    model_name,
    provider_name: Optional[str] = None,
):
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)
    prompt = pm.render_file_metadata(
        filename=filename,
        file_type=file_type,
        context=context,
        refined_prompt=refined_prompt,
        tree=tree,
        file_content=file_content,
        file_output_format=file_output_format,
    )

    # Determine provider from model_name or use provided provider_name
    if provider_name is None:
        if model_name.startswith("models/"):
            provider_name = "google"
        else:
            provider_name = InferenceManager.get_default_provider()

    provider = InferenceManager.create_provider(provider_name)

    messages = [{"role": "user", "content": prompt}]
    response = provider.call_model(messages, model=model_name)

    return provider.extract_text(response)


def generate_file_content(
    context,
    filepath,
    refined_prompt,
    tree,
    json_file_name,
    file_output_format,
    pm,
    model_name,
    provider_name: Optional[str] = None,
):
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)
    prompt = pm.render_file_content(
        filename=filename,
        file_type=file_type,
        context=context,
        refined_prompt=refined_prompt,
        tree=tree,
        file_output_format=file_output_format,
    )

    # Determine provider from model_name or use provided provider_name
    if provider_name is None:
        if model_name.startswith("models/"):
            provider_name = "google"
        else:
            provider_name = InferenceManager.get_default_provider()

    provider = InferenceManager.create_provider(provider_name)

    messages = [{"role": "user", "content": prompt}]
    response = provider.call_model(messages, model=model_name)
    response_text = provider.extract_text(response)
    cleaned_output = clean_agent_output(response_text)
    return cleaned_output


def dfs_tree_and_gen(
    root,
    refined_prompt,
    tree_structure,
    project_name,
    model_name,
    current_path="",
    parent_context="",
    json_file_name="",
    metadata_dict=None,
    dependency_analyzer=None,
    file_output_format="",
    max_workers=20,
    output_base_dir="",
    pm=None,
    on_status=None,
):
    count = 0
    if metadata_dict is None:
        metadata_dict = {}

    if pm is None:
        pm = PromptManager()

    lock = Lock()
    first_file_generated = {"done": False, "start_time": None}
    work_queue = Queue()
    root_value = root.value if root else "root"

    if output_base_dir:
        root_full_path = os.path.join(output_base_dir, root_value)
    else:
        root_full_path = root_value

    if not os.path.exists(root_full_path):
        os.makedirs(root_full_path, exist_ok=True)

    for child in root.children:
        work_queue.put(
            {
                "node": child,
                "current_path": root_value,
                "parent_context": parent_context,
                "is_top_level": False,
                "output_base_dir": output_base_dir,
                "root_value": root_value,
            }
        )

    def process_work_item(work_item):
        node = work_item["node"]
        current_path = work_item["current_path"]
        parent_context = work_item["parent_context"]
        work_output_base_dir = work_item.get("output_base_dir", output_base_dir)
        root_val = work_item.get("root_value", root.value if root else "root")

        clean_name = node.value.split("#")[0].strip()
        clean_name = clean_name.replace("(", "").replace(")", "")
        clean_name = clean_name.replace("uploads will go here, e.g., ", "")

        relative_path = (
            os.path.join(current_path, clean_name) if current_path else clean_name
        )

        if work_output_base_dir:
            full_path = os.path.join(work_output_base_dir, relative_path)
        else:
            full_path = relative_path

        context = (
            os.path.join(parent_context, clean_name) if parent_context else clean_name
        )

        if node.is_file:
            return process_file(
                node,
                full_path,
                context,
                refined_prompt,
                tree_structure,
                json_file_name,
                file_output_format,
                metadata_dict,
                dependency_analyzer,
                lock,
                pm,
                on_status,
                model_name,
                count,
                first_file_generated,
            )
        else:
            return process_directory(
                node,
                full_path,
                context,
                work_queue,
                work_output_base_dir,
                lock,
                root_val,
                on_status,
            )

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
                done, not_done = wait(
                    active_futures, timeout=1, return_when=FIRST_COMPLETED
                )
                for future in done:
                    try:
                        result = future.result()
                        if result and "children" in result:
                            for child_work in result["children"]:
                                work_queue.put(child_work)
                    except Exception:
                        pass
                active_futures = set(not_done)
def process_file(
    node,
    full_path,
    context,
    refined_prompt,
    tree_structure,
    json_file_name,
    file_output_format,
    metadata_dict,
    model_name,
    dependency_analyzer,
    lock,
    pm,
    count,
    on_status=None,
    first_file_generated=None,
):
    try:
        parent_dir = os.path.dirname(full_path)
        if parent_dir:
            with lock:
                if not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)

        if should_generate_content(full_path):
            if first_file_generated and not first_file_generated["done"]:
                with lock:
                    if not first_file_generated["done"]:
                        first_file_generated["start_time"] = time.time()

            start_time = time.time()
            content = generate_file_content(
                context=context,
                filepath=full_path,
                refined_prompt=refined_prompt,
                tree=tree_structure,
                json_file_name=json_file_name,
                file_output_format=file_output_format,
                pm=pm,
                model_name=model_name,
            )
            end_time = time.time()
            elapsed = end_time - start_time

            if first_file_generated and not first_file_generated["done"]:
                with lock:
                    if not first_file_generated["done"]:
                        first_file_time = end_time - first_file_generated["start_time"]
                        first_file_generated["done"] = True
                        if on_status:
                            on_status(
                                "first_file_time",
                                f"First file generated in {first_file_time:.2f}s",
                                time=first_file_time,
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
                model_name=model_name,
            )

            with lock:
                with open(full_path, "w") as f:
                    f.write(content)

                if full_path not in metadata_dict:
                    metadata_dict[full_path] = []
                metadata_dict[full_path].append({"description": metadata})

    except Exception as e:
        print(f"Error processing file {full_path}: {e}")

    return None


def process_directory(
    node,
    full_path,
    context,
    work_queue,
    output_base_dir="",
    lock=None,
    root_value="",
    on_status=None,
):
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
                "node": child,
                "current_path": rel_path,
                "parent_context": context,
                "is_top_level": False,
                "output_base_dir": output_base_dir,
                "root_value": root_value,
            }
            children_work.append(child_work)

        return {"children": children_work}

    except OSError:
        return None


def initial_software_blueprint_eval(
    prompt, pm, model_name, provider_name: Optional[str] = None
):
    # Determine provider from model_name or use provided provider_name
    if provider_name is None:
        if model_name.startswith("models/"):
            provider_name = "google"
        else:
            provider_name = InferenceManager.get_default_provider()

    provider = InferenceManager.create_provider(provider_name)
    system_instruction = pm.render_software_blueprint(user_prompt=prompt)

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt},
    ]

    response = provider.call_model(messages, model=model_name)
    resp = provider.extract_text(response)

    match = re.search(r"\{.*\}", resp, re.DOTALL)

    if match:
        clean_json_str = match.group(0)
        try:
            data = json.loads(clean_json_str)
            # Sanitize project name: replace spaces with underscores
            if "projectDetails" in data and "projectName" in data["projectDetails"]:
                data["projectDetails"]["projectName"] = data["projectDetails"][
                    "projectName"
                ].replace(" ", "_")
            system_info = get_system_info()
            data["systemInfo"] = system_info
            return data
        except json.JSONDecodeError:
            raise ValueError("Failed to parse JSON from model response.")
    return None


def folder_structure(
    project_overview, pm, model_name, provider_name: Optional[str] = None
):
    # Determine provider from model_name or use provided provider_name
    if provider_name is None:
        if model_name.startswith("models/"):
            provider_name = "google"
        else:
            provider_name = InferenceManager.get_default_provider()

    provider = InferenceManager.create_provider(provider_name)
    system_instruction = pm.render_folder_structure(project_overview=project_overview)

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": json.dumps(project_overview)},
    ]

    response = provider.call_model(messages, model=model_name)
    return provider.extract_text(response)


def files_format(
    project_overview,
    folder_structure,
    pm,
    model_name,
    provider_name: Optional[str] = None,
):
    # Determine provider from model_name or use provided provider_name
    if provider_name is None:
        if model_name.startswith("models/"):
            provider_name = "google"
        else:
            provider_name = InferenceManager.get_default_provider()

    provider = InferenceManager.create_provider(provider_name)
    system_instruction = pm.render_file_format(
        project_overview=project_overview, folder_structure=folder_structure
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": json.dumps(project_overview)},
    ]

    response = provider.call_model(messages, model=model_name)
    return provider.extract_text(response)


def generate_tree(resp, project_name="root"):
    content = resp.strip().replace("```", "").strip()
    lines = content.split("\n")
    tree_line_pattern = re.compile(
        r"^(?:│\s*)*(?:├──\s*|└──\s*)?([^│├└#\n]+?)(?:/)?(?:\s*#.*)?$", re.IGNORECASE
    )

    root = None
    root_name = None
    root_line_index = -1

    for i, line in enumerate(lines):
        if not line.strip():
            continue

        match = tree_line_pattern.match(line.strip())
        if match:
            root_name = match.group(1).strip().rstrip("/")
        else:
            root_name = line.strip()
            if "#" in root_name:
                root_name = root_name.split("#")[0].strip()
            root_name = re.sub(r"[│├└─\s]+", "", root_name).strip().rstrip("/")

        # Replace spaces with underscores in folder names
        if root_name:
            root_name = root_name.replace(" ", "_")
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
        while (
            temp_line.startswith("│   ")
            or temp_line.startswith("    ")
            or temp_line.startswith("│ ")
            or temp_line.startswith("    ")
        ):
            temp_line = temp_line[4:]
            indent += 1

        match = tree_line_pattern.match(line.strip())
        if not match:
            name = line.strip()
            if "#" in name:
                name = name.split("#")[0].strip()
            name = re.sub(r"[│├└─\s]+", "", name).strip()
        else:
            name = match.group(1).strip()

        name = name.rstrip("/")

        # Replace spaces with underscores in folder/file names
        name = name.replace(" ", "_")

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


def eval_generate_project(user_prompt, output_base_dir, model_name, on_status=None):
    metrics = {}
    from utils.dependencies import DependencyAnalyzer, DependencyFeedbackLoop
    from docker.testing import run_docker_testing
    from docker.eval_generator import DockerTestFileGeneratorEval
    from utils.error_tracker import ErrorTracker
    from datetime import datetime

    first_file_time_captured = {"time": None}

    def emit(event_type, message, **kwargs):
        if event_type == "first_file_time" and "time" in kwargs:
            first_file_time_captured["time"] = kwargs["time"]
        if on_status:
            on_status(event_type, message, **kwargs)

    pm = PromptManager()

    emit("step", "Creating software blueprint...")
    blueprint_start = time.time()
    software_blueprint = initial_software_blueprint_eval(user_prompt, pm, model_name)
    blueprint_end = time.time()
    metrics["blueprint_generation_time"] = blueprint_end - blueprint_start
    print("software bluepint is done!!")

    emit("step", "Creating folder structure...")
    folder_start = time.time()
    folder_struc = folder_structure(software_blueprint, pm, model_name)
    folder_end = time.time()
    metrics["folder_structure_generation_time"] = folder_end - folder_start
    print("folder structure is done!!")

    emit("step", "Creating file format contracts...")
    format_start = time.time()
    file_format = files_format(software_blueprint, folder_struc, pm, model_name)
    format_end = time.time()
    metrics["file_format_generation_time"] = format_end - format_start
    print("file format is done!!")

    emit("step", "Building project tree and generating files...")
    folder_tree = generate_tree(folder_struc, project_name="")
    dependency_analyzer = DependencyAnalyzer()
    os.makedirs(output_base_dir, exist_ok=True)
    json_file_name = os.path.join(output_base_dir, "projects_metadata.json")
    metadata_dict = {}

    file_gen_start = time.time()
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
        model_name=model_name,
        on_status=emit,
    )
    file_gen_end = time.time()
    metrics["all_files_generation_time"] = file_gen_end - file_gen_start
    metrics["first_file_generation_time"] = first_file_time_captured["time"]

    print("DFS tree and generation is done!!")

    project_root_path = os.path.join(output_base_dir, folder_tree.value)

    if not os.path.exists(project_root_path):
        return None

    with open(json_file_name, "w") as f:
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

    docker_gen_start = time.time()
    try:
        test_gen = DockerTestFileGeneratorEval(
            project_root=project_root_path,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            metadata_dict=metadata_dict,
            dependency_analyzer=dependency_analyzer,
            pm=pm,
            on_status=on_status,
            model_name=model_name,
        )

        test_gen_results = test_gen.generate_all()
        metrics["dockerfile_generation_success"] = True
    except Exception as e:
        metrics["dockerfile_generation_success"] = False
        metrics["dockerfile_generation_error"] = str(e)

    docker_gen_end = time.time()
    metrics["dockerfile_generation_time"] = docker_gen_end - docker_gen_start

    emit("step", "Starting dependency analysis for entire project...")
    dep_analysis_start = time.time()
    dependency_analyzer.analyze_project_files(
        project_root_path, folder_tree=folder_tree, folder_structure=folder_struc
    )
    dep_analysis_end = time.time()
    metrics["dependency_analysis_time"] = dep_analysis_end - dep_analysis_start

    emit("step", "Extracting external dependencies and generating dependency files...")
    dep_file_gen_start = time.time()
    try:
        from utils.dependency_file_generator import (
            extract_all_external_dependencies,
            DependencyFileGenerator,
        )

        # Extract all external dependencies from all files in the project
        external_dependencies = extract_all_external_dependencies(
            dependency_analyzer, project_root_path
        )

        # Generate dependency files using the coding agent
        dep_file_gen = DependencyFileGenerator(
            project_root=project_root_path,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            external_dependencies=external_dependencies,
            pm=pm,
            model_name=model_name,
            on_status=on_status,
        )

        dep_file_results = dep_file_gen.generate_all()
        metrics["dependency_file_generation_success"] = True
        metrics["dependency_files_generated"] = dep_file_results.get(
            "generated_files", []
        )

        # Re-analyze project files to include the newly generated dependency files
        dependency_analyzer.analyze_project_files(
            project_root_path, folder_tree=folder_tree, folder_structure=folder_struc
        )
    except Exception as e:
        metrics["dependency_file_generation_success"] = False
        metrics["dependency_file_generation_error"] = str(e)
        print(f"Error generating dependency files: {e}")

    dep_file_gen_end = time.time()
    metrics["dependency_file_generation_time"] = dep_file_gen_end - dep_file_gen_start

    # Dependency resolution disabled for ablation study
    emit("step", "Skipping dependency resolution (disabled)...")
    error_tracker = ErrorTracker(project_root_path)
    dep_results = {
        "success": True,
        "iterations": 0,
        "remaining_errors": [],
        "skipped": True,
    }
    metrics["dependency_resolution_time"] = 0.0
    metrics["dependency_resolution_success"] = True
    metrics["dependency_resolution_iterations"] = 0
    metrics["dependency_remaining_errors_count"] = 0

    emit("step", "Running Docker testing pipeline...")

    docker_test_start = time.time()
    docker_results = run_docker_testing(
        project_root=project_root_path,
        software_blueprint=software_blueprint,
        folder_structure=folder_struc,
        file_output_format=file_output_format,
        pm=pm,
        error_tracker=error_tracker,
        dependency_analyzer=dependency_analyzer,
        on_status=on_status,
    )
    docker_test_end = time.time()

    metrics["docker_testing_time"] = docker_test_end - docker_test_start
    metrics["docker_build_success"] = docker_results.get("build_success", False)
    metrics["docker_build_iterations"] = docker_results.get("build_iterations", 0)
    metrics["docker_tests_success"] = docker_results.get("tests_success", False)
    metrics["docker_test_iterations"] = docker_results.get("test_iterations", 0)

    if "build_errors" in docker_results:
        metrics["docker_build_errors"] = docker_results["build_errors"]

    if "test_errors" in docker_results:
        metrics["docker_test_errors"] = docker_results["test_errors"]

    for file_path, entries in metadata_dict.items():
        deps = dependency_analyzer.get_dependency_details(file_path)
        for entry in entries:
            entry["couples_with"] = deps

    with open(json_file_name, "w") as f:
        json.dump(metadata_dict, f, indent=4)

    end_time = time.time()
    start_time = (
        file_gen_start
        - metrics["blueprint_generation_time"]
        - metrics["folder_structure_generation_time"]
        - metrics["file_format_generation_time"]
    )
    elapsed = end_time - start_time

    overall_success = dep_results.get("success", False) and docker_results.get(
        "success", False
    )

    if os.path.exists(json_file_name):
        try:
            os.remove(json_file_name)
        except Exception:
            pass

    metrics["total_elapsed_time"] = elapsed
    metrics["overall_success"] = overall_success
    metrics["model_name"] = model_name
    metrics["timestamp"] = datetime.now().isoformat()
    metrics["user_prompt"] = user_prompt

    total_files = sum(1 for _, _, files in os.walk(project_root_path) for _ in files)
    metrics["total_files_generated"] = total_files

    eval_dir = os.path.join("evals", model_name)
    os.makedirs(eval_dir, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    metrics_filename = f"{model_name}_{timestamp_str}.json"
    metrics_filepath = os.path.join(eval_dir, metrics_filename)

    with open(metrics_filepath, "w") as f:
        json.dump(metrics, f, indent=4)

    print(f"\nmetrics saved to: {metrics_filepath}")

    return {
        "project_path": project_root_path,
        "dependency_resolution": dep_results,
        "docker_testing": docker_results,
        "success": overall_success,
        "elapsed_time": elapsed,
        "metrics": metrics,
        "metrics_file": metrics_filepath,
    }


def get_prompt_mapping():
    return {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
        5: "fifth",
        6: "sixth",
        7: "seventh",
        8: "eigth",
        9: "ninth",
        10: "tenth",
    }


def load_prompt_from_template(language, prompt_number):
    prompt_mapping = get_prompt_mapping()
    prompt_name = prompt_mapping.get(prompt_number)

    if not prompt_name:
        raise ValueError(f"Invalid prompt number: {prompt_number}")

    eval_prompts_dir = os.path.join(
        os.path.dirname(__file__), "prompts", "eval", language
    )

    if not os.path.exists(eval_prompts_dir):
        raise ValueError(f"Language directory not found: {language}")

    template_file = f"{prompt_name}.j2"
    template_path = os.path.join(eval_prompts_dir, template_file)

    if not os.path.exists(template_path):
        if language == "go" and prompt_name == "third":
            template_file = "thrid.j2"
            template_path = os.path.join(eval_prompts_dir, template_file)

        if not os.path.exists(template_path):
            raise ValueError(f"Template not found: {template_path}")

    env = Environment(loader=FileSystemLoader(eval_prompts_dir))
    template = env.get_template(template_file)
    prompt = template.render()

    return prompt.strip()


def eval_generate_project_batch(
    prompt_number, output_base_dir, model_name, on_status=None
):
    languages = ["cuda", "go", "rust", "typescript"]
    results = {}

    for language in languages:
        if on_status:
            on_status("step", f"Starting evaluation for {language.upper()}")

        try:
            prompt = load_prompt_from_template(language, prompt_number)

            language_output_dir = os.path.join(output_base_dir, language)

            result = eval_generate_project(
                user_prompt=prompt,
                output_base_dir=language_output_dir,
                model_name=model_name,
                on_status=on_status,
            )

            if result and "metrics" in result:
                result["metrics"]["language"] = language
                result["metrics"]["prompt_number"] = prompt_number

            results[language] = result

            if on_status:
                success = result.get("success", False) if result else False
                status_msg = f"Completed {language.upper()}: {'SUCCESS' if success else 'FAILED'}"
                on_status("step", status_msg)

        except Exception as e:
            if on_status:
                on_status("error", f"Error in {language.upper()}: {str(e)}")
            results[language] = None

    return results
