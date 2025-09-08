import os
import pathlib
import google.generativeai as genai
from tree_thing import TreeNode

def gen_file_content(context, file_path, project_desc, project_name, is_top_level=True, desc="", folder_structure=None):
    prompt = f"""
    You are an expert-level software engineer with deep expertise across all programming languages, frameworks, and file formats. You excel at generating production-ready code that integrates seamlessly within existing project architectures.

    Task
    Generate the complete file content for the specified file path within the given project context.

    Input Parameters
    Project Description: {project_desc}

    File Path: {file_path}

    Project Context: {context}

    File Purpose: {desc}

    Project Name: {project_name}

    Folder structure: {folder_structure}

    Generation Requirements
    Code Quality Standards
    Write clean, maintainable, and efficient code following industry best practices

    Implement proper error handling and edge case management

    Use appropriate design patterns and architectural principles

    Ensure type safety and proper validation where applicable

    Follow language-specific conventions and style guides

    Project Integration
    Analyze the file path to determine the exact file type and required implementation approach

    Ensure seamless integration with existing project structure and dependencies

    Maintain consistency with project naming conventions and organizational patterns

    Consider inter-file dependencies and module relationships

    Implement proper imports, exports, and namespace management

    Context Awareness
    Leverage the project description to understand the overall system architecture

    Use the provided context to make informed decisions about implementation details

    Ensure the file serves its intended purpose within the broader application ecosystem

    Consider scalability, performance, and maintainability requirements

    File-Specific Optimization
    Configuration Files: Use proper syntax, validation, and environment-specific settings

    Source Code: Implement robust logic with appropriate abstractions and modularity

    Documentation: Create comprehensive, accurate, and well-structured content

    Database Files: Follow schema best practices and optimization principles

    API Definitions: Ensure proper endpoint design, validation, and documentation

    Build Scripts: Implement efficient, cross-platform compatible automation

    Output Specifications
    Generate only the raw file content exactly as it would appear in the actual file

    No markdown formatting, code blocks, explanations, or additional commentary

    Ensure immediate compatibility with the target development environment

    Validate that the content matches the expected file format and structure

    Maintain proper indentation, spacing, and formatting conventions

    Technical Excellence
    Implement security best practices and input validation

    Optimize for performance while maintaining code readability

    Use appropriate data structures and algorithms for the specific use case

    Ensure cross-platform compatibility where relevant

    Consider memory management and resource utilization

    Generate the complete, production-ready file content that perfectly fulfills the specified requirements and integrates flawlessly into the project architecture.
    """

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            genai.configure(api_key="AIzaSyDqA_anmBc5of17-j2OOjy1_R6Fv_mwu5Y")
        else:
            genai.configure(api_key=api_key)

        resp = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(contents=prompt)
        return resp.text
    
    except Exception as e:
        print(f"Error generating content for {file_path}: {e}")
        file_ext = pathlib.Path(file_path).suffix
        if file_ext == '.py':
            return f'# {file_path}\n# Generated file for {project_name}\n\n# TODO: Implement functionality\npass\n'
        elif file_ext == '.md':
            return f'# {pathlib.Path(file_path).stem}\n\nGenerated documentation for {project_name}\n'
        elif file_ext == '.json':
            return '{\n  "name": "' + project_name + '",\n  "version": "1.0.0"\n}\n'
        else:
            return f'// Generated file for {project_name}\n// TODO: Implement functionality\n'


def dfs_tree_and_gen(root: TreeNode, project_desc, project_name, parent_context, current_path, folder_structure, is_top_level=True, dependency_analyzer=None):
    if not isinstance(root, TreeNode):
        raise TypeError(f"Expected TreeNode, got {type(root)}. Value: {root}")
    
    clean_name = root.value.split('#')[0].strip()
    clean_name = clean_name.replace('(', '').replace(')', '')
    clean_name = clean_name.replace('uploads will go here, e.g., ', '')
    clean_name = clean_name.rstrip('/')

    if is_top_level:
        full_path = os.path.join(project_name, clean_name)
    else:
        full_path = os.path.join(current_path, clean_name)

    context = os.path.join(parent_context, clean_name) if parent_context else clean_name

    if root.is_file and root.value != project_name:
        parent_dir = os.path.dirname(full_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        #check if this path already exists as directory, or else just the one line is enough
        if os.path.exists(full_path) and os.path.isdir(full_path):
            print(f"Warning: {full_path} already exists as directory, skipping file creation")
            return full_path
        
        content = gen_file_content(
            context=context,
            file_path=full_path,
            project_desc=project_desc,
            project_name=project_name,
            is_top_level=is_top_level,
            desc=getattr(root, 'description', ''),
            folder_structure=folder_structure
        )
        
        try:
            with open(full_path, "w", encoding='utf-8') as f:
                f.write(content)

            if dependency_analyzer:
                dependency_analyzer.analyze_file_dependencies(full_path, content)
            print("Generated file:", full_path)
        except Exception as e:
            print(f"Error writing file {full_path}: {e}")
    else:
        os.makedirs(full_path, exist_ok=True)
        print("Generated directory:", full_path)

        for child in root.children:
            dfs_tree_and_gen(
                child,
                project_desc,
                project_name,
                context,
                full_path,
                folder_structure,  
                is_top_level=False,
                dependency_analyzer=dependency_analyzer
            )

    return full_path


