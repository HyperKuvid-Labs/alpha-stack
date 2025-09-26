from folder_tree import TreeNode,DependencyAnalyzer
import os
from gen_file import GENERATABLE_FILES,GENERATABLE_FILENAMES
from google import genai
from genai_client import get_client
from concurrent.futures import as_completed, ThreadPoolExecutor, wait, FIRST_COMPLETED
from typing import Optional
from _thread import LockType
from threading import Lock
from queue import Queue
from collections import deque
#should think of a better way to do this
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

def generate_file_metadata(context: str, filepath: str, refined_prompt: str, tree: str, json_file_name: str, file_content: str,file_output_format: str) -> str:
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)

    prompt = f"""You are analyzing a file from a project. Generate a detailed yet concise metadata description that captures its purpose, structure, and relationships.
        **File Information**
        - File Name: {filename}
        - File Type: {file_type} (e.g., .py, .html, .css)
        - Project Location: {context} (e.g., models, views, static/css, templates/)
        - Project Idea: {refined_prompt}
        - Project Structure:
        {tree}
        - File Content:
        {file_content}
        - File_Format
        {file_output_format}
        **What to include in your response:**
        -Summary: A concise 2–3 sentence summary of the file's primary purpose and its role within the overall application.
        -Core Components: Identify the main building blocks defined within the file based on its type:
        - For backend or logic files (e.g., .py, .js, .java, .go, .rb): Mention the key classes, functions, APIs, controllers, services, or data models.
        - For frontend UI files (e.g., .html, .jsx, .vue, .svelte): Describe the UI component or view it renders, the data it's expected to display, and any parent/child component relationships or layout inheritance.
        - For styling or asset files (e.g., .css, .scss, .js, .ts): Explain the primary styling rules, animations, or client-side logic it contributes to the user interface.
        - Internal Dependencies: List which other files within this project the file is directly coupled with (e.g., through import/require statements, component nesting, or API calls).
        - External Dependencies: Mention any third-party libraries, frameworks, or external packages this file relies on (e.g., react, express, pandas, axios).
        **Response Format:**
        - Return only the raw description text (no markdown, bullets, or headings).
        - Do not include any code or formatting artifacts.
    """
    client=get_client()
    resp = client.models.generate_content(model="gemini-2.5-flash-preview-05-20", contents=prompt)

    return resp.text

def generate_file_content(context: str, filepath: str, refined_prompt: str, tree: str, json_file_name: str,file_output_format:str) -> str:
    
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)
    
    prompt = f"""
                You are a senior developer. Your task is to generate production-ready file content for the technical projects based on specific file requirements and project context[1].

                ## Analysis Phase
                First, analyze the provided parameters:
                - **File Name**: `{filename}` - Determine the exact purpose and scope
                - **File Type** file_type: `{file_type}` - Apply type-specific best practices
                - **Project Context**: `{context}` - Understand the file's role in the application architecture
                - **Project Idea** refined_prompt: `{refined_prompt}` - Align content with business requirements
                - **Folder Structure** : `{tree}` - Ensure consistency with project organization
                - **Fileoutput format**: `{file_output_format}`- Ensure the consistency of exports and imports from each of the file
            
                ## Content Generation Template
            
                Generate the complete file content for filenameof type file_type within the context of for  project described in refined_prompt.
                Generate the complete file content based on the provided file name, file type, project context, project description, and folder structure.
                Core Requirements
                Architectural Compliance: Follow established best practices and conventions for the specified technology stack (e.g., framework idioms, language-specific patterns).
                Consistency: Maintain consistency with the provided folder structure.
                Dependencies: Include only necessary imports, require statements, or module dependencies.
                Readability: Use appropriate docstrings, comments, and clear naming for all variables, functions, and classes.
                Code Quality: Ensure the generated code is modular, maintainable, and production-ready.
                Frontend & Data Handling Guidelines
                UI Framework: Specify the UI framework and version (e.g., 'Bootstrap 5', 'Tailwind CSS', 'Material-UI').
                Icon Library: Specify the icon library to be used (e.g., 'Bootstrap Icons', 'Font Awesome').
                Client-Side Scripting: Define the client-side scripting approach (e.g., 'Use vanilla JavaScript for all logic,' 'Use Axios for API calls,' 'No jQuery').
                Data Submission: Define clear contracts for data submission, such as the expected structure of a JSON request body.
                Validation: Implement robust client-side and server-side validation and user-friendly error handling.
                General Implementation Guidelines
                Separation of Concerns: Avoid mixing logic and presentation (e.g., no inline JavaScript in HTML, no business logic in UI components).
                Responsiveness: Default to a mobile-first responsive design.
                Accessibility: Ensure accessibility best practices are followed, such as providing alt text for all images.
                User Experience: Implement loading states for all asynchronous operations, such as form submissions and data fetching.
                File-Role Specific Requirements
                Disclaimer: Please note that the roles and file extensions mentioned below are common examples. This template is designed to be versatile and can be adapted for any file type relevant to your project.
            
                Configuration Files (.env, .json, .yaml, config.js)
                Define how secrets and environment variables are managed (e.g., 'Direct declaration, no .env files').
                Structure configuration for different environments (development, production).
                API / Routing Files
                Define route structures and naming conventions (e.g., router.post('/api/resource', handlerFunction)).
                Specify how request handlers or controllers are imported and registered.
                Data Model / Schema Files
                Define data structures using the appropriate ORM/ODM classes or schema definitions (e.g., Mongoose Schema, SQLAlchemy Model, Prisma Schema).
                Specify field types, validation rules, default values, and relationships.
                Include necessary helper methods (e.g., __str__, .toJSON()).
                Business Logic / Controller Files
                Adhere to the specified programming paradigm (e.g., 'Function-based handlers only,' 'Use class-based services').
                Handle incoming requests, process data, interact with data models, and return appropriate responses (e.g., JSON, rendered templates).
                UI Component / Template Files (.html, .jsx, .vue, .svelte)
                Utilize a component-based architecture with an emphasis on reusability.
                Implement layout inheritance or composition where applicable.
                Clearly separate props/inputs from internal state.
                Styling Files (.css, .scss, .less)
                Follow a consistent naming convention (e.g., BEM, CUBE CSS).
                Organize styles modularly, often co-located with their respective components.
                Client-Side Scripting Files (.js, .ts)
                Implement AJAX/Fetch for asynchronous data operations.
                Manage application state effectively.
                Handle user events and perform DOM manipulation cleanly.
                Output Requirements
                - The first line of the output must be the programming language name (e.g., "python", "javascript", "html", "css").
                - Starting from the second line, return only the raw file content as it would appear in the actual file.
                - Do not wrap code in markdown formatting or code blocks.
                - Do not include explanations or extra commentary — just the language name on the first line and then the file content.
                - The content must be immediately usable in a project using the specified technology.
                - Follow the exact syntax and conventions for the specified file type."""
    client=get_client()
    response = client.models.generate_content(model="gemini-2.5-flash-preview-05-20", contents=prompt)
    # metadata = generate_file_metadata(context, filepath, refined_prompt, tree, json_file_name, response.text) 
    cleaned_output=clean_agent_output(response.text)
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
    max_workers: int = 10 # Limit concurrent workers
) -> None:
    """
    Non-recursive approach using a work queue to avoid thread pool deadlock
    """
    if metadata_dict is None:
        metadata_dict = {}
    
    lock = Lock()
    work_queue = Queue()
    
    # Initial work item
    work_queue.put({
        'node': root,
        'current_path': current_path,
        'parent_context': parent_context,
        'is_top_level': True
    })
    
    def process_work_item(work_item):
        """Process a single work item"""
        node = work_item['node']
        current_path = work_item['current_path']
        parent_context = work_item['parent_context']
        is_top_level = work_item['is_top_level']
        
        clean_name = node.value.split('#')[0].strip()
        clean_name = clean_name.replace('(', '').replace(')', '')
        clean_name = clean_name.replace('uploads will go here, e.g., ', '')

        if is_top_level:
            full_path = os.path.join(project_name, clean_name)
        else:
            full_path = os.path.join(current_path, clean_name)

        context = os.path.join(parent_context, clean_name) if parent_context else clean_name

        if node.is_file:
            return process_file(node, full_path, context, refined_prompt, tree_structure, 
                              json_file_name, file_output_format, metadata_dict, 
                              dependency_analyzer, lock)
        else:
            return process_directory(node, full_path, context, work_queue)
    
    # Process work items with limited thread pool
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        active_futures = set()
        
        while not work_queue.empty() or active_futures:
            # Submit new work while we have capacity and work available
            while len(active_futures) < max_workers and not work_queue.empty():
                work_item = work_queue.get()
                future = executor.submit(process_work_item, work_item)
                active_futures.add(future)
            
            # Process completed futures
            if active_futures:
                done, not_done = wait(active_futures, timeout=1, return_when=FIRST_COMPLETED)
                for future in done:
                    try:
                        result = future.result()
                        if result and 'children' in result:
                            # Add children to work queue
                            for child_work in result['children']:
                                work_queue.put(child_work)
                    except Exception as e:
                        print(f"Error in work item: {e}")
                active_futures = set(not_done)

def process_file(node, full_path, context, refined_prompt, tree_structure, 
                json_file_name, file_output_format, metadata_dict, 
                dependency_analyzer, lock):
    """Process a single file"""
    try:
        parent_dir = os.path.dirname(full_path)
        if parent_dir and not os.path.exists(parent_dir):
            with lock:  # Ensure thread-safe directory creation
                os.makedirs(parent_dir, exist_ok=True)

        if should_generate_content(full_path):
            # Generate content (this is the time-consuming part)
            content = generate_file_content(
                context=context,
                filepath=full_path,
                refined_prompt=refined_prompt,
                tree=tree_structure,
                json_file_name=json_file_name,
                file_output_format=file_output_format
            )
            
            metadata = generate_file_metadata(
                context=context,
                filepath=full_path,
                refined_prompt=refined_prompt,
                tree=tree_structure,
                json_file_name=json_file_name,
                file_content=content,
                file_output_format=file_output_format
            )
            
            # Thread-safe file operations
            with lock:
                with open(full_path, 'w') as f:
                    f.write(content)
                
                if dependency_analyzer:
                    dependency_analyzer.add_file(full_path, content=content, 
                                               folder_structure=tree_structure)
                
                if full_path not in metadata_dict:
                    metadata_dict[full_path] = []
                metadata_dict[full_path].append({
                    "description": metadata
                })
            
            print(f"Generated content for {full_path}")
        else:
            print(f"Skipping file: {full_path}")
            
    except Exception as e:
        print(f"Error generating file {full_path}: {e}")
    
    return None

def process_directory(node, full_path, context, work_queue):
    """Process a directory and add children to work queue"""
    try:
        os.makedirs(full_path, exist_ok=True)
        print(f"Created directory: {full_path}")
        
        # Add children to work queue instead of recursive submission
        children_work = []
        for child in node.children:
            child_work = {
                'node': child,
                'current_path': full_path,
                'parent_context': context,
                'is_top_level': False
            }
            children_work.append(child_work)
        
        return {'children': children_work}
        
    except OSError as e:
        print(f"Error creating directory {full_path}: {e}")
        return None