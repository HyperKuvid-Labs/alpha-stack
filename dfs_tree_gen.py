from folder_tree import TreeNode, DependencyAnalyzer
import os
from gen_file import GENERATABLE_FILES, GENERATABLE_FILENAMES
from genai_client import get_client
from concurrent.futures import as_completed, ThreadPoolExecutor, wait, FIRST_COMPLETED
from typing import Optional
from threading import Lock
from queue import Queue, Empty
from prompt_manager import PromptManager


def should_generate_content(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    return ext in GENERATABLE_FILES or filename in GENERATABLE_FILENAMES
def clean_agent_output(content: str) -> str:
    if not content:
        return ""
    lines = content.strip().splitlines()
    if len(lines) > 1:
        cleaned = "\n".join(lines[1:])
    else:
        cleaned = ""

    return cleaned.strip() + "\n"

def generate_file_metadata(
    context: str,
    filepath: str,
    refined_prompt: str,
    tree: str,
    json_file_name: str,
    file_content: str,
    file_output_format: str,
    pm: PromptManager
) -> str:
    """
    Generate file metadata using Jinja2 template
    
    Args:
        context: Project context path
        filepath: Full path to the file
        refined_prompt: Project description
        tree: Folder structure string
        json_file_name: Name of the metadata JSON file
        file_content: The generated file content
        file_output_format: File format contracts
        pm: PromptManager instance
    
    Returns:
        Metadata description string
    """
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
    
    client = get_client()
    resp = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20",
        contents=prompt
    )
    
    return resp.text

def generate_file_content(
    context: str,
    filepath: str,
    refined_prompt: str,
    tree: str,
    json_file_name: str,
    file_output_format: str,
    pm: PromptManager
) -> str:
    """
    Generate file content using Jinja2 template
    
    Args:
        context: Project context path
        filepath: Full path to the file
        refined_prompt: Project description
        tree: Folder structure string
        json_file_name: Name of the metadata JSON file
        file_output_format: File format contracts
        pm: PromptManager instance
    
    Returns:
        Generated file content
    """
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
    
    client = get_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20",
        contents=prompt
    )
    
    cleaned_output = clean_agent_output(response.text)
    return cleaned_output

def dfs_tree_and_gen(
    root: TreeNode,
    refined_prompt: str,
    tree_structure: str,
    project_name: str,
    current_path: str = "",
    parent_context: str = "",
    json_file_name: str = "",
    metadata_dict: dict = None,
    dependency_analyzer: DependencyAnalyzer = None,
    file_output_format: str = "",
    max_workers: int = 10,
    output_base_dir: str = "",
    pm: PromptManager = None
) -> None:
    """
    Non-recursive approach using a work queue to avoid thread pool deadlock
    
    Args:
        root: Root TreeNode
        refined_prompt: Project description
        tree_structure: Folder structure string
        project_name: Name of the project
        current_path: Current path in traversal
        parent_context: Parent context path
        json_file_name: Name of metadata JSON file
        metadata_dict: Dictionary to store metadata
        dependency_analyzer: Dependency analyzer instance
        file_output_format: File format contracts
        max_workers: Maximum number of concurrent workers
        pm: PromptManager instance
    """
    if metadata_dict is None:
        metadata_dict = {}
    
    if pm == None:
        pm = PromptManager(templates_dir="prompts")
    
    lock = Lock()
    work_queue = Queue()
    root_value = root.value if root else "root"
    
    if output_base_dir:
        root_full_path = os.path.join(output_base_dir, root_value)
    else:
        root_full_path = root_value
    
    if not os.path.exists(root_full_path):
        os.makedirs(root_full_path, exist_ok=True)
        print(f"📁 Created root directory: {root_full_path}")
    
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
        """Process a single work item"""
        node = work_item['node']
        current_path = work_item['current_path']
        parent_context = work_item['parent_context']
        is_top_level = work_item['is_top_level']
        work_output_base_dir = work_item.get('output_base_dir', output_base_dir)
        root_value = work_item.get('root_value', root.value if root else "root")
        
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
                dependency_analyzer, lock, pm
            )
        else:
            return process_directory(node, full_path, context, work_queue, work_output_base_dir, lock, root_value)
    
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
                    except Exception as e:
                        print(f"Error in work item: {e}")
                active_futures = set(not_done)

def process_file(
    node, full_path, context, refined_prompt, tree_structure,
    json_file_name, file_output_format, metadata_dict,
    dependency_analyzer, lock, pm
):
    """Process a single file"""
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
                pm=pm
            )
            
            metadata = generate_file_metadata(
                context=context,
                filepath=full_path,
                refined_prompt=refined_prompt,
                tree=tree_structure,
                json_file_name=json_file_name,
                file_content=content,
                file_output_format=file_output_format,
                pm=pm
            )
            
            with lock:
                with open(full_path, 'w') as f:
                    f.write(content)
                
                if dependency_analyzer:
                    dependency_analyzer.add_file(
                        full_path,
                        content=content,
                        folder_structure=tree_structure
                    )
                
                if full_path not in metadata_dict:
                    metadata_dict[full_path] = []
                metadata_dict[full_path].append({
                    "description": metadata
                })
            
            print(f"✅ Generated content for {full_path}")
        else:
            print(f"⏭️  Skipping file: {full_path}")
            
    except Exception as e:
        print(f"❌ Error generating file {full_path}: {e}")
    
    return None

def process_directory(node, full_path, context, work_queue, output_base_dir="", lock=None, root_value=""):
    """Process a directory and add children to work queue"""
    try:
        if lock:
            with lock:
                if not os.path.exists(full_path):
                    os.makedirs(full_path, exist_ok=True)
        else:
            os.makedirs(full_path, exist_ok=True)
        print(f"📁 Created directory: {full_path}")
        
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
        
    except OSError as e:
        print(f"Error creating directory {full_path}: {e}")
        return None