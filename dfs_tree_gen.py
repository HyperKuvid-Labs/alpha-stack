from folder_tree import TreeNode,DependencyAnalyzer
import os
from gen_file import GENERATABLE_FILES,GENERATABLE_FILENAMES
from google import genai
from resp_clean import clean_ai_generated_code
from genai_client import get_client
#should think of a better way to do this
def should_generate_content(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    return ext in GENERATABLE_FILES or filename in GENERATABLE_FILENAMES
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
    
    prompt = f"""# Refined Django File Content Generation prompt

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

    Generate the complete file content for filenameof type file_type within the context of `{context}` for the Django project described in refined_prompt.
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
    Return only the raw file content as it would appear in the actual file.
        Do not include any markdown formatting, code blocks, or additional explanations.
       The content must be immediately usable in a project using the specified technology.
       Follow the exact syntax and conventions for the specified file type.
       The output should not contain any other things dont add the the language name in the output"""
    client=get_client()
    response = client.models.generate_content(model="gemini-2.5-flash-preview-05-20", contents=prompt)
    # metadata = generate_file_metadata(context, filepath, refined_prompt, tree, json_file_name, response.text)
    
    # Clean AI-generated code to remove markdown artifacts
    
    return response.text


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
    is_top_level: bool = True,
    file_output_format:str=""
) -> None:
    # if metadata_dict is None:
    #     if json_file_name and os.path.exists(json_file_name):
    #         try:
    #             with open(json_file_name, 'r') as f:
    #                 metadata_dict = json.load(f)
    #         except Exception:
    #             metadata_dict = {}
    #     else:
    #         metadata_dict = {}

    clean_name = root.value.split('#')[0].strip()
    clean_name = clean_name.replace('(', '').replace(')', '')
    clean_name = clean_name.replace('uploads will go here, e.g., ', '')

    # Corrected path logic
    if is_top_level:
        full_path = os.path.join(project_name, clean_name)
    else:
        full_path = os.path.join(current_path, clean_name)

    context = os.path.join(parent_context, clean_name) if parent_context else clean_name

    # Traverse context into nested dict
    # path_part = context.split('/')
    # current_dict = metadata_dict
    # for part in path_part[:-1]:
    #     if part and part not in current_dict:
    #         current_dict[part] = {}
    #     if part:
    #         current_dict = current_dict[part]

    if root.is_file:
        parent_dir = os.path.dirname(full_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        if  should_generate_content(full_path):
            try:
                content =generate_file_content(
                    context=context,
                    filepath=full_path,
                    refined_prompt=refined_prompt,
                    tree=tree_structure,
                    json_file_name=json_file_name,
                    file_output_format=file_output_format
                )
                metadata = generate_file_metadata(
                    context = context,
                    filepath = full_path,
                    refined_prompt=refined_prompt,
                    tree=tree_structure,
                    json_file_name=json_file_name,
                    file_content=content,
                    file_output_format=file_output_format
                )
                with open(full_path, 'w') as f:
                    f.write(content)
                # parts = context.split('/')
                # current = metadata_dict[project_name]
                # for part in parts[:-1]:
                #     current = current.setdefault(part, {})
                # current[parts[-1]] = {
                #     "type": "file",
                #     "description": metadata,
                #     "path": full_path
                # }

                if dependency_analyzer:
                    dependency_analyzer.add_file(full_path, content=content,folder_structure=tree_structure)
                
                metadata_dict[project_name].append({
                    "path": full_path,
                    "description": metadata,
                })
                print(f"Generated content for {full_path}")

                # current_dict[clean_name] = {
                #     "type": "file",
                #     "description": metadata,
                #     "path": full_path
                # }
            except Exception as e:
                print(f"Error generating file {full_path}: {e}")
        else:
            print(f"Skipping file: {full_path}")

    else:
        try:
            os.makedirs(full_path, exist_ok=True)
            print(f"Created directory: {full_path}")
            # current_dict[clean_name] = {"type": "directory"}
            for child in root.children:
                dfs_tree_and_gen(
                    root=child,
                    refined_prompt=refined_prompt,
                    tree_structure=tree_structure,
                    project_name=project_name,
                    current_path=full_path,
                    parent_context=context,
                    json_file_name=json_file_name,
                    metadata_dict=metadata_dict,
                    dependency_analyzer=dependency_analyzer,
                    is_top_level=False,
                    file_output_format=file_output_format
                )
        except OSError as e:
            print(f"Error creating directory {full_path}: {e}")
            return
