import google.generativeai as genai
import string
import os 
import json
import re
from tqdm import tqdm
import networkx as nx
import ast 
from typing import List, Set
import sys
import subprocess

api_key = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=api_key)

def clean_ai_generated_code(content: str) -> str:
    if not content:
        return content
        
    content = re.sub(r'^```python\s*\n?', '', content, flags=re.MULTILINE)
    content = re.sub(r'^```\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'```python', '', content)
    content = re.sub(r'```', '', content)
    
    content = content.strip()
    
    if content and not content.endswith('\n'):
        content += '\n'
        
    return content

#models
# models/embedding-gecko-001
# models/gemini-1.0-pro-vision-latest
# models/gemini-pro-vision
# models/gemini-1.5-pro-latest
# models/gemini-1.5-pro-001
# models/gemini-1.5-pro-002
# models/gemini-1.5-pro
# models/gemini-1.5-flash-latest
# models/gemini-1.5-flash-001
# models/gemini-1.5-flash-001-tuning
# models/gemini-1.5-flash
# models/gemini-1.5-flash-002
# models/gemini-1.5-flash-8b
# models/gemini-1.5-flash-8b-001
# models/gemini-1.5-flash-8b-latest
# models/gemini-1.5-flash-8b-exp-0827
# models/gemini-1.5-flash-8b-exp-0924
# models/gemini-2.5-pro-exp-03-25
# models/gemini-2.5-pro-preview-03-25
# models/gemini-2.5-flash-preview-04-17
# models/gemini-2.5-flash-preview-05-20
# models/gemini-2.5-flash-preview-04-17-thinking
# models/gemini-2.5-pro-preview-05-06
# models/gemini-2.0-flash-exp
# models/gemini-2.0-flash
# models/gemini-2.0-flash-001
# models/gemini-2.0-flash-exp-image-generation
# models/gemini-2.0-flash-lite-001
# models/gemini-2.0-flash-lite
# models/gemini-2.0-flash-preview-image-generation
# models/gemini-2.0-flash-lite-preview-02-05
# models/gemini-2.0-flash-lite-preview
# models/gemini-2.0-pro-exp
# models/gemini-2.0-pro-exp-02-05

GENERATABLE_FILES = {
    '.py', '.html', '.css', '.js', '.md', '.yml', '.yaml', '.env', '.txt', '.png', '.ico', '.sh'
}
GENERATABLE_FILENAMES = {
    'Dockerfile', 'README.md', '.gitignore', 'requirements.txt', 'docker-compose.yml', '.env'
}

class TreeNode:
    def __init__(self, value):
        self.value = value
        self.children = []
        self.is_file = False

    def add_child(self, child_node):
        print("Adding child node:", child_node.value)
        self.children.append(child_node)
    
    def print_tree(self, level=0, prefix=""):
        if level == 0:
            print(self.value)
        else:
            print(prefix + "├── " + self.value)
        
        for i, child in enumerate(self.children):
            is_last = i == len(self.children) - 1
            child.print_tree(
                level + 1, 
                prefix + ("    " if is_last else "│   ")
            )

    def dfsTraverse(self):
        print("Current node value: ", self.value)
        for child in self.children:
            child.dfsTraverse()

class DependencyAnalyzer:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_file(self, file_path: str, content: str):
        self.graph.add_node(file_path)
        dependencies = self.extract_dependencies(file_path, content)
        for dep in dependencies:
            self.graph.add_edge(file_path, dep)
    
    def extract_dependencies(self, file_path: str, content: str) -> Set[str]:
        dependencies = set()
        file_dir = os.path.dirname(file_path)
        
        if file_path.endswith("py"):
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            dependencies.add(alias.name)
                        
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module
                        level = node.level

                        if level > 0:
                            rel_path = "." + level + (f".{module}" if module else "")
                            rel_module = self.resolve_relative_import(file_dir, rel_path)
                            if rel_module:
                                dependencies.add(rel_module)
                        elif module:
                            dependencies.add(module)

            except Exception as e:
                print(f"Error parsing {file_path}: {e}")

        elif file_path.endswith(".html"):
            includes = re.findall(r'{%\s*(include|extends)\s+[\'"]([^\'"]+)[\'"]\s*%}', content)
            for _, templates in includes:
                dependencies.add(templates)
            
        elif file_path.endswith(".css"):
            imports = re.findall(r'@import\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in imports:
                dependencies.add(imp)
            
        elif file_path.endswith(".js"):
            imports = re.findall(r'import\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in imports:
                dependencies.add(imp)
        
        return dependencies
    
    def resolve_relative_import(self, file_path: str, rel_path: str) -> str:
        parts = file_path.split(os.sep)
        rel_depth = rel_path.count('.')
        module_name = rel_path.replace('.', '')
        base_parts = parts[:-rel_depth]
        if module_name:
            base_parts.append(module_name.replace('.', os.sep))
        resolved_path = os.path.join(*base_parts)
        if not resolved_path.endswith('.py'):
            resolved_path += '.py'
        return resolved_path if os.path.exists(resolved_path) else None
    
    def get_dependencies(self, file_path: str) -> List[str]: 
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        return list(self.graph.predecessors(file_path))
    
    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)
    
    def visualize_graph(self):
        try:
            import matplotlib.pyplot as pl
            pos = nx.spring_layout(self.graph)
            nx.draw(self.graph, pos, with_labels=True, arrows=True, node_size=2000, node_color='lightblue', font_size=10, font_color='black', edge_color='gray')
            pl.title("Dependency Graph")
            pl.show()
        except ImportError:
            print("punda matplotlib is not installed. Skipping graph visualization.")

def refine_prompt(prompt: str) -> str:
    resp = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents = f"""
            You are a senior Django architect. Your task is to take a high-level project idea and generate a detailed prompt that instructs a language model to output a production-ready Django folder structure, including all directories and file names, but no file contents or code.

Analysis Phase
First, analyze the provided {prompt}:

If it lacks clarity, technical scope, or business requirements, elaborate on it appropriately by inferring the most logical system architecture

If the prompt is already detailed and comprehensive, return it as-is

Consider the target audience, scale, and complexity level based on the project description

Refined Prompt Template
Project Name: <project_name>

Generate a complete production-ready folder structure (no code or file contents) for a Django project named <project_name>.

Project Overview
This project is a <detailed system description with technical context>, designed to serve <target user base> with the following core capabilities:

Key Features & Workflows:

<Feature 1>: <Brief workflow description>

<Feature 2>: <Brief workflow description>

<Feature 3>: <Brief workflow description>

<Additional features as needed>

User Roles & Permissions:

<Role 1>: <Specific capabilities and access levels>

<Role 2>: <Specific capabilities and access levels>

<Role 3>: <Specific capabilities and access levels>

Django Architecture Requirements
Core Apps Structure:

accounts – Authentication, user registration, profile management, and role-based access control

<domain_app_1> – <Primary business logic description>

<domain_app_2> – <Secondary business logic description>

dashboard – Role-specific dashboards with analytics and management interfaces

core – Shared utilities, context processors, middleware, and project-wide configurations

<additional_apps_as_needed> – <Purpose and scope>

Production-Grade Structure:

Root directory with manage.py for server management

Configuration directory (config/ or <project_name>_config/) containing all Django settings

Modular app architecture with clear separation of concerns

Standard asset organization: static/, templates/, media/

Development and deployment configurations

Technical Implementation Guidelines
Form Handling:

No Django forms.py files - implement all forms using HTML <form> tags with name attributes

Extract form data in views using request.POST.get('field_name') pattern

Use JavaScript AJAX for form submissions where enhanced UX is required

Implement proper form validation and error handling

Frontend Standards:

No inline JavaScript - All JS logic in external .js files under static/js/

Bootstrap Latest Version for all styling and responsive design

Bootstrap Icons for all iconography

Mobile-first responsive design as default

Latest CDN versions for all external libraries (SweetAlert, etc.)

Proper loading states for all form submissions and navigation

Accessible alt text for all image elements

Database Design:

Use TextField for any uncertain field sizes in models

Implement proper foreign key relationships and constraints

Include migration files structure for each app

File Organization:

Each app contains: migrations/, static/, templates/, tests/, and standard Django files

App-specific templates in <app_name>/templates/<app_name>/

App-specific static files in <app_name>/static/<app_name>/

Shared templates and static files in root-level directories

Required Project Files
Include these essential files in the structure:

requirements.txt - Python dependencies

.env.example and .env - Environment configuration

README.md - Project documentation

.gitignore - Version control exclusions

Dockerfile and docker-compose.yml - Containerization

.github/workflows/ - CI/CD pipeline configuration

Output Format
Return only the complete folder structure in a clean tree view format showing:

All directories and subdirectories

All file names (without content)

Proper indentation to show hierarchy

Standard Django file conventions

Do not include any code, file contents, or implementation details.

Example Application
Input: events management portal

Expected Refined Output:

Project Name: events_management_portal

Generate a complete production-ready folder structure (no code or file contents) for a Django project named events_management_portal.

Project Overview
This project is a comprehensive Event Management System designed to serve event organizers, attendees, and administrators with streamlined event lifecycle management, from creation to post-event analytics.

Key Features & Workflows:

Event Discovery: Users browse, search, and filter events by category, date, location, and price

Event Management: Organizers create, edit, publish, and manage their events with media uploads

Registration System: Attendees register for events with payment processing and ticket generation

Admin Moderation: Administrators approve events, manage users, and oversee platform operations

Analytics Dashboard: Role-specific dashboards with event metrics, attendance tracking, and revenue reports

User Roles & Permissions:

Attendees: Browse events, register/purchase tickets, manage bookings, view event history

Organizers: Create and manage events, view attendee lists, access event analytics, handle refunds

Administrators: Moderate all content, manage user accounts, oversee platform settings, generate reports

Django Architecture Requirements
Core Apps Structure:

accounts – Authentication, user registration, profile management, and role-based access control

events – Event models, creation, editing, publishing, and lifecycle management

bookings – Registration system, payment processing, ticket generation, and attendee management

dashboard – Role-specific dashboards with analytics, metrics, and management interfaces

core – Shared utilities, context processors, middleware, and project-wide configurations

notifications – Email/SMS notifications, alerts, and communication management

[Continue with all technical requirements as specified in the template...]

Return only the complete folder structure in tree view format. Do not include any file content or code.
"""
    )

    return resp.text

# for model in genai.list_models():
#     print(model.name)


# response = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
#     contents = '''Generate the folder structure only (no files or code) for a Django project named event_portal.
#     The project is an Event Management System with the following key features:

#     Users can register, log in, and browse upcoming events.

#     Organizers can create and manage events.

#     Admins can approve or reject submitted events.

#     Includes a dashboard for both users and organizers.

#     Use Django best practices: apps should be modular and reusable.

#     Include standard folders for static files, templates, media, and configuration.

#     Use apps like: accounts, events, dashboard, and core.

#     Follow conventional Django naming and project structuring.
#     Return just the whole end to end production-based folder structure as a tree view along with the file names, not any code'''
# )

def generate_folder_struct(prompt: str) -> str:
    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents = prompt
    )

    return resp.text

def generate_file_metadata(context: str, filepath: str, refined_prompt: str, tree: str, json_file_name: str, file_content: str) -> str:
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)

    prompt = f"""You are analyzing a file from a Django project. Generate a detailed yet concise metadata description that captures its purpose, structure, and relationships.

        **File Information**
        - File Name: {filename}
        - File Type: {file_type} (e.g., .py, .html, .css)
        - Project Location: {context} (e.g., models, views, static/css, templates/)
        - Project Idea: {refined_prompt}
        - Project Structure:
        {tree}
        - File Content:
        {file_content}

        **What to include in your response:**
        1. A concise 2–3 sentence summary of what this file does and how it fits into the Django project.
        2. If it's a Python file:
        - Mention key classes, functions, models, or signal handlers.
        3. If it's a template (HTML):
        - Describe the view/component it supports and any template inheritance.
        4. If it's a static file (CSS/JS):
        - Explain the styling or client-side logic it contributes to.
        5. List **which other files or modules this file is directly coupled with**, either through imports, usage, or template inclusion.
        6. Mention any external packages or Django modules (e.g., `django.contrib.auth`) used here.

        **Response Format:**
        - Return only the raw description text (no markdown, bullets, or headings).
        - Do not include any code or formatting artifacts.
    """

    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents = prompt
    )

    return resp.text

def generate_file_content(context: str, filepath: str, refined_prompt: str, tree: str, json_file_name: str) -> str:
    
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)
    
    prompt = f"""# Refined Django File Content Generation Prompt

You are a senior Django developer. Your task is to generate production-ready file content for Django projects based on specific file requirements and project context[1].

## Analysis Phase
First, analyze the provided parameters:
- **File Name**: `{filename}` - Determine the exact purpose and scope
- **File Type**: `{file_type}` - Apply type-specific best practices
- **Project Context**: `{context}` - Understand the file's role in the application architecture
- **Project Idea**: `{refined_prompt}` - Align content with business requirements
- **Folder Structure**: `{tree}` - Ensure consistency with project organization

## Content Generation Template

Generate the complete file content for `{filename}` of type `{file_type}` within the context of `{context}` for the Django project described in `{refined_prompt}`.

### Core Requirements

**Django Architecture Compliance:**
- Follow Django best practices specific to the file type and context
- Maintain consistency with the provided folder structure `{tree}`
- Include only necessary imports and dependencies
- Use appropriate docstrings and inline comments for code clarity
- Ensure modular, maintainable, and production-ready code

### Form Handling Standards
- **No Django forms.py** - Implement all forms using HTML `` tags with `name` attributes
- Extract form data using `request.POST.get('field_name')` pattern in views
- Use vanilla JavaScript AJAX for enhanced form submissions (no jQuery)
- Implement proper form validation and error handling

### Frontend Implementation Guidelines
- **No inline JavaScript** - All JS logic in external files
- **Bootstrap Latest Version** for styling and responsive design
- **Bootstrap Icons** for all iconography
- **Mobile-first responsive design** as default
- **Latest CDN versions** for external libraries (SweetAlert, etc.)
- **Loading states** for all form submissions and navigation
- **Accessible alt text** for all image elements

### File-Type Specific Requirements

#### Python Files

**For settings.py:**
- **No .env files** - Direct declaration of all configuration values
- **SQLite3 database** as default backend
- **BASE_DIR** pointing to manage.py location (standard Django structure)
- **INSTALLED_APPS** containing only default Django apps and project-created apps
- Import custom apps as `"appname"` not `"appname.apps.AppnameConfig"`
- Standard middleware, templates, static, and media configurations

**For urls.py:**
- Import `path` first
- Import admin URLs
- Include all app URLs created by the developer
- Include static and media URL patterns based on settings
- Import views as `from .views import *`
- URL patterns format: `path('route/', view_function, name='url_name')`

**For admin.py:**
- Simple model registration: `admin.site.register(ModelName)`
- Import models as `from .models import *`
- No custom admin forms or complex admin views

**For models.py:**
- **Class-based models** only: `class ModelName(models.Model):`
- Set `null=True, blank=True` for most fields to avoid validation errors
- Use `TextField` for uncertain field sizes
- Include proper `__str__` methods
- Add type hints where appropriate

**For views.py:**
- **Function-based views** only (no class-based views)
- Import all dependencies: `from .models import *`
- Include type hints for function parameters and return values
- Clean, modular, and maintainable code structure
- Proper error handling and user feedback

#### Template Files (HTML)
- Use Django template inheritance (`{"% extends %"}, {"% block %"}`)
- Write semantic, accessible HTML
- **No inline JavaScript** - reference external JS files
- Use Django template tags and filters appropriately
- Bootstrap integration for responsive design
- Proper form structure with `name` attributes

#### CSS Files
- Modular, reusable styles
- Follow BEM or consistent naming conventions
- Responsive design principles
- Bootstrap customizations in separate files
- Clean, organized structure

#### JavaScript Files
- Clean, modular vanilla JavaScript (no jQuery)
- Unobtrusive JavaScript practices
- AJAX implementations for form handling
- Loading state management
- Proper error handling and user feedback
- Comprehensive comments for clarity

### Output Requirements
- Return **only the raw file content** as it would appear in the actual file
- No markdown formatting, code blocks, or additional explanations
- Content must be immediately usable in a Django project
- Follow exact syntax and conventions for the specified file type
- Ensure compatibility with the provided project structure and context

### Example Usage

**Input Parameters:**
- File Name: `views.py`
- File Type: `Python`
- Project Context: `accounts app`
- Project Idea: `User management system with role-based access`
- Folder Structure: `[provided tree structure]`

**Expected Output:**
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import *

def user_login(request):
    ""Handle user authentication and login""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')
    
    return render(request, 'accounts/login.html')
**Generate the complete, production-ready file content based on the provided parameters. Return only the raw code without any formatting or explanations.**
    """
    
    response = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents=prompt
    )

    # metadata = generate_file_metadata(context, filepath, refined_prompt, tree, json_file_name, response.text)
    
    # Clean AI-generated code to remove markdown artifacts
    cleaned_content = clean_ai_generated_code(response.text)
    
    return cleaned_content

def should_generate_content(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    return ext in GENERATABLE_FILES or filename in GENERATABLE_FILENAMES

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
    is_top_level: bool = True
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

        if should_generate_content(full_path):
            try:
                content =generate_file_content(
                    context=context,
                    filepath=full_path,
                    refined_prompt=refined_prompt,
                    tree=tree_structure,
                    json_file_name=json_file_name
                )
                metadata = generate_file_metadata(
                    context = context,
                    filepath = full_path,
                    refined_prompt=refined_prompt,
                    tree=tree_structure,
                    json_file_name=json_file_name,
                    file_content=content
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
                    dependency_analyzer.add_file(full_path, content=content)
                
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
                    is_top_level=False
                )
        except OSError as e:
            print(f"Error creating directory {full_path}: {e}")
            return

    # if is_top_level and json_file_name:
    #     with open(json_file_name, 'w') as f:
    #         json.dump(metadata_dict, f, indent=4)

def check_file_coupleness(metadata_dict, file_content, file_path, actual_dependencies):
    prompt = f"""
    # Refined Django Code Coupling Review Prompt

    You are an expert Django code reviewer specializing in dependency analysis and architectural coupling verification.

    ## Review Objective
    Your task is to perform a comprehensive coupling accuracy assessment by analyzing the relationship between:
    1. **Actual code dependencies** - Real imports, references, and cross-module usage in the file
    2. **Declared metadata couplings** - The `couples_with` list in project metadata
    3. **Static analysis results** - Dependencies detected through automated code analysis

    ## Analysis Parameters

    **Target File**: `{file_path}`

    **File Content**:
    ```
    {file_content}
    ```

    **Declared Metadata Couplings** (`couples_with`):
    ```
    {metadata_dict}
    ```

    **Statically Detected Dependencies**:
    ```
    {actual_dependencies}
    ```

    ## Comprehensive Analysis Framework

    ### 1. Code Dependency Analysis
    Examine the file for:
    - **Direct imports**: `import`, `from ... import` statements
    - **Dynamic imports**: `importlib`, `__import__()` calls
    - **Template references**: Template tags, includes, extends
    - **URL references**: `reverse()`, `reverse_lazy()`, URL name usage
    - **Model relationships**: Foreign keys, many-to-many, generic relations
    - **Signal connections**: Django signals and handlers
    - **Middleware dependencies**: Custom middleware usage
    - **Context processor references**: Template context dependencies
    - **Static file references**: CSS, JS, image references
    - **Configuration dependencies**: Settings usage from other apps

    ### 2. Cross-Reference Validation
    Compare and validate:
    - **Completeness**: Are all actual dependencies captured in metadata?
    - **Accuracy**: Are declared couplings actually used in the code?
    - **Precision**: Are there false positives in the declared couplings?
    - **Consistency**: Do static analysis results align with manual inspection?

    ### 3. Django-Specific Coupling Patterns
    Consider Django-specific dependencies:
    - **App-level couplings**: Cross-app model imports, view references
    - **Template inheritance**: Base templates from other apps
    - **URL pattern includes**: URLconf dependencies
    - **Admin customizations**: Admin class imports and registrations
    - **Form dependencies**: Form class imports and usage
    - **Serializer references**: DRF serializer imports (if applicable)
    - **Permission classes**: Custom permission imports
    - **Utility functions**: Shared utility imports across apps

    ### 4. Error Detection
    Identify potential issues:
    - **Circular dependencies**: Mutual imports between modules
    - **Missing imports**: Referenced but not imported modules
    - **Unused imports**: Imported but never used modules
    - **Incorrect import paths**: Wrong module paths or names
    - **Version compatibility**: Django version-specific imports
    - **Syntax errors**: Malformed import statements

    ## Output Requirements

    Return **ONLY** this exact JSON format:

    {{
        "correctness": "correct" or "incorrect",
        "changes_needed": "detailed explanation of discrepancies, missing entries, extra entries, or errors (empty string if everything is accurate)"
    }}


    ### Response Guidelines

    **For "correct" assessment:**
    - All actual dependencies are properly declared in metadata
    - No unused or incorrect entries in declared couplings
    - Static analysis results align with manual inspection
    - No syntax or logical errors detected

    **For "incorrect" assessment:**
    - Provide specific details about:
    - Missing dependencies in metadata
    - Extra/unused entries in metadata
    - Discrepancies between static analysis and declared couplings
    - Syntax or import errors
    - Circular dependency issues
    - Django-specific coupling problems

    ## Example Scenarios

    ### Example 1 - Perfect Alignment
    {{
        "correctness": "correct",
        "changes_needed": ""
    }}


    ### Example 2 - Missing Dependencies
    {{
        "correctness": "incorrect",
        "changes_needed": "The file imports `from accounts.models import User` and `from core.utils import send_notification` but neither `accounts.models` nor `core.utils` are listed in the declared metadata couples_with list."
    }}


    ### Example 3 - Extra Metadata Entries
    {{
        "correctness": "incorrect",
        "changes_needed": "Metadata declares coupling with `events.serializers` but this module is not imported or used anywhere in the file. Also, the file uses `django.contrib.auth.views.LoginView` which is missing from the declared couplings."
    }}


    ### Example 4 - Static Analysis Mismatch
    {{
        "correctness": "incorrect",
        "changes_needed": "Static analysis detected dependency on `payments.models.Transaction` but this is not reflected in either the actual imports or declared metadata. Additionally, metadata lists `notifications.tasks` but static analysis shows it's only referenced in comments, not actual code."
    }}


    ### Example 5 - Syntax Errors
    {{
        "correctness": "incorrect",
        "changes_needed": "Import statement `from .models import` is incomplete and will cause a syntax error. The file also references `User` model without importing it from django.contrib.auth.models or accounts.models."
    }}

    ## Analysis Execution

    Perform the coupling accuracy review by:
    1. **Parsing all imports** and references in the provided file content
    2. **Cross-referencing** with declared metadata couplings
    3. **Validating** against static analysis results
    4. **Identifying discrepancies** and potential issues
    5. **Providing actionable feedback** for corrections

    **Return only the JSON response with your assessment.*
    """
    
    try:
        resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
            contents = prompt
        )
        
        if not resp or not resp.text:
            return "undetermined", "AI model returned empty response"
            
    except Exception as e:
        print(f"Error calling AI model for coupling check: {e}")
        return "undetermined", f"Could not analyze coupling due to AI error: {e}"

    cleaned_response = resp.text.strip('`').replace('json\n', '').strip()
    
    try:
        data = json.loads(cleaned_response)
        correctness = data.get("correctness", "undetermined")
        changes_needed = data.get("changes_needed", "")
        return correctness, changes_needed
    except json.JSONDecodeError:
        return "undetermined", f"Could not parse response: {resp.text}. Please check the model's output format."
    

def validate_imports_exist(file_path: str, content: str, project_files: set):
    invalid_imports = []

    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    module_parts = node.module.split('.')
                    potential_file = os.path.join(*module_parts) + '.py'

                    if potential_file not in project_files:
                        invalid_imports.append(f"Import '{node.module}' in {file_path} does not exist in the project files.")

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module_parts = alias.name.split('.')
                    potential_file = os.path.join(*module_parts) + '.py'

                    if potential_file not in project_files and not alias.name.startswith('django'):
                        invalid_imports.append(f"Import {alias.name}")

    except SyntaxError as e:
        pass

    return invalid_imports

def get_project_files(metadata_dict, project_name) -> set:
    project_files = set()
    for entry in metadata_dict.get(project_name, []):
        if entry["path"].endswith('.py'):
            rel_path = os.path.relpath(entry["path"], project_name)
            project_files.add(rel_path)
    return project_files

def validate_python_syntax(file_path: str, content: str) -> List[str]:
    issues = []
    
    try:
        ast.parse(content)
    except SyntaxError as e:
        issues.append(f"Syntax error in {file_path}: {e}")
        return issues
    
    try:
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None and node.level == 0:
                    issues.append(f"Incomplete import statement in {file_path}")
                
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if not alias.name or alias.name.strip() == "":
                        issues.append(f"Empty import name in {file_path}")
        
        defined_names = set()
        used_names = set()
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                defined_names.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                defined_names.add(node.id)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
        
        django_builtins = {'models', 'forms', 'views', 'admin', 'urls', 'settings', 'HttpResponse', 'render', 'redirect'}
        python_builtins = {'print', 'str', 'int', 'float', 'list', 'dict', 'tuple', 'set', 'len', 'range', 'enumerate'}
        
        undefined_vars = used_names - defined_names - django_builtins - python_builtins
        if undefined_vars and len(undefined_vars) < 10:  
            for var in undefined_vars:
                if not var.startswith('_') and var not in ['request', 'self', 'cls']:
                    issues.append(f"Potentially undefined variable '{var}' in {file_path}")
    
    except Exception as e:
        issues.append(f"Error during syntax validation of {file_path}: {e}")
    
    return issues

def comprehensive_file_validation(file_path: str, content: str, project_files: set) -> List[str]:
    all_issues = []
    
    syntax_issues = validate_python_syntax(file_path, content)
    all_issues.extend(syntax_issues)
    
    import_issues = validate_imports_exist(file_path, content, project_files)
    all_issues.extend(import_issues)
    
    naming_issues = valid_django_naming_conventions(content, file_path)
    all_issues.extend(naming_issues)

    django_issues = validate_django_specific_issues(file_path, content)
    all_issues.extend(django_issues)
    
    return all_issues

def validate_django_specific_issues(file_path: str, content: str) -> List[str]:
    issues = []
    filename = os.path.basename(file_path)
    
    try:
        tree = ast.parse(content)
        
        if filename == 'models.py':
            has_models_import = any(
                isinstance(node, ast.ImportFrom) and node.module == 'django.db' 
                for node in ast.walk(tree)
            )
            if not has_models_import and 'models.Model' in content:
                issues.append(f"Missing 'from django.db import models' in {file_path}")
        
        elif filename == 'views.py':
            has_shortcuts_import = any(
                isinstance(node, ast.ImportFrom) and node.module == 'django.shortcuts'
                for node in ast.walk(tree)
            )
            if ('render' in content or 'redirect' in content) and not has_shortcuts_import:
                issues.append(f"Missing 'from django.shortcuts import render, redirect' in {file_path}")
        
        elif filename == 'urls.py':
            has_path_import = any(
                isinstance(node, ast.ImportFrom) and node.module == 'django.urls' and 
                any(alias.name == 'path' for alias in node.names)
                for node in ast.walk(tree)
            )
            if 'path(' in content and not has_path_import:
                issues.append(f"Missing 'from django.urls import path' in {file_path}")
        
        elif filename == 'admin.py':
            has_admin_import = any(
                isinstance(node, ast.ImportFrom) and node.module == 'django.contrib' and
                any(alias.name == 'admin' for alias in node.names)
                for node in ast.walk(tree)
            )
            if 'admin.site.register' in content and not has_admin_import:
                issues.append(f"Missing 'from django.contrib import admin' in {file_path}")
    
    except Exception as e:
        issues.append(f"Error during Django-specific validation of {file_path}: {e}")
    
    return issues

def valid_django_naming_conventions(code, file_path):
    issues = []

    django_patterns = {
        'views.py': {
            'class_suffix': ['View', 'ListView', 'DetailView', 'CreateView', 'UpdateView', 'DeleteView'],
            'function_prefix': ['get_', 'post_', 'put_', 'delete_']
        },
        'models.py': {
            'class_suffix': ['Model'],
            'field_patterns': ['CharField', 'IntegerField', 'DateTimeField']
        },
        'forms.py': {
            'class_suffix': ['Form', 'ModelForm']
        }
    }
    
    try:
        tree = ast.parse(code)
        file_type = os.path.basename(file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                
                if file_type == 'views.py':
                    if 'updateview' in class_name.lower() and not class_name.endswith('UpdateView'):
                        issues.append(f"Malformed view name: {class_name} should probably be {class_name.replace('updateview', 'UpdateView').replace('goalupdate', 'GoalUpdate')}")
                    
                    elif 'createview' in class_name.lower() and not class_name.endswith('CreateView'):
                        issues.append(f"Malformed view name: {class_name} should probably be {class_name.replace('createview', 'CreateView')}")
                    
                    elif 'listview' in class_name.lower() and not class_name.endswith('ListView'):
                        issues.append(f"Malformed view name: {class_name} should probably be {class_name.replace('listview', 'ListView')}")
                
                if file_type == 'models.py' and not any(base.id == 'Model' for base in node.bases if isinstance(base, ast.Name)):
                    issues.append(f"Model class {class_name} should inherit from models.Model")
    
    except SyntaxError as e:
        issues.append(f"Syntax error in file: {e}")
    
    return issues

    django_patterns = {
        'views.py': {
            'class_suffix': ['View', 'ListView', 'DetailView', 'CreateView', 'UpdateView', 'DeleteView'],
            'function_prefix': ['get_', 'post_', 'put_', 'delete_']
        },
        'models.py': {
            'class_suffix': ['Model'],
            'field_patterns': ['CharField', 'IntegerField', 'DateTimeField']
        },
        'forms.py': {
            'class_suffix': ['Form', 'ModelForm']
        }
    }
    
    try:
        tree = ast.parse(code)
        file_type = os.path.basename(file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                
                if file_type == 'views.py':
                    if 'updateview' in class_name.lower() and not class_name.endswith('UpdateView'):
                        issues.append(f"Malformed view name: {class_name} should probably be {class_name.replace('updateview', 'UpdateView').replace('goalupdate', 'GoalUpdate')}")
                    
                    elif 'createview' in class_name.lower() and not class_name.endswith('CreateView'):
                        issues.append(f"Malformed view name: {class_name} should probably be {class_name.replace('createview', 'CreateView')}")
                    
                    elif 'listview' in class_name.lower() and not class_name.endswith('ListView'):
                        issues.append(f"Malformed view name: {class_name} should probably be {class_name.replace('listview', 'ListView')}")
                
                if file_type == 'models.py' and not any(base.id == 'Model' for base in node.bases if isinstance(base, ast.Name)):
                    issues.append(f"Model class {class_name} should inherit from models.Model")
    
    except SyntaxError as e:
        issues.append(f"Syntax error in file: {e}")
    
    return issues
                                               
def refine_for_comprehensive_fixes(file_content, changes_needed, validation_issues):
    prompt = f"""
    You are an expert Django developer.

    Your task is to correct the following Django project file to fix ALL identified issues comprehensively.

    ---

    **Original File Content**:
    {file_content}

    ---

    **Coupling/Dependency Issues**:
    {changes_needed}

    ---

    **Validation Issues**:
    {validation_issues}

    ---

    **Requirements**:
    Fix ALL issues mentioned above including:
    1. **Import Issues**:
        - Missing imports: Add required imports
        - Invalid imports: Remove or correct non-existent imports
        - Incomplete imports: Complete partial import statements
        - Django-specific imports: Add missing Django framework imports
    
    2. **Syntax Issues**:
        - Fix any Python syntax errors
        - Complete incomplete statements
        - Fix malformed code structures
    
    3. **Django-Specific Issues**:
        - Ensure proper model inheritance (models.Model)
        - Add required Django imports for views, admin, urls
        - Fix Django naming conventions
        - Ensure proper field definitions in models
    
    4. **Code Quality**:
        - Remove unused imports
        - Fix undefined variable references
        - Ensure proper function/class definitions
        - Add proper error handling where needed
    
    **Critical Requirements**:
    - Generate COMPLETE, FUNCTIONAL, ERROR-FREE Django code
    - Maintain original logic and functionality
    - Follow Django best practices
    - Ensure all imports are correct and complete
    - Make sure the code can run without syntax or import errors
    - Use proper Django patterns and conventions

    ---

    **Output Format**:
    - Return ONLY the corrected file content as raw code
    - No markdown, no comments, no extra text
    - Must be immediately usable in a Django project

    ---

    **Goal**: The output should be production-ready Django code with ZERO errors.
    """

    response = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents=prompt
    )

    # Clean AI-generated code to remove markdown artifacts
    cleaned_content = clean_ai_generated_code(response.text)

    return cleaned_content
    prompt = f"""
    You are an expert Django developer.

    Your task is to correct the following Django project file so that its **imports and references** properly match the declared couplings and dependency expectations, based on feedback from a static analysis and metadata validation.

    ---

    **Original File Content**:
    {file_content}

    ---

    **Correction Feedback**:
    {changes_needed}

    ---

    **Requirements**:
    - Fix **only the issues mentioned in the Correction Feedback** — including:
        - Missing or incorrect imports.
        - Imports of non-existent files or modules — these should be removed.
        - Typographical errors in import statements or class/function names.
        - Syntactical errors in the file that prevent it from running correctly.
    - Ensure that all imports and references are logically correct and semantically aligned with the metadata.
    - If an import is missing, **add it**.
    - If an import is incorrect, **correct it**.
    - If an import is redundant or not used, **remove it**.
    - If an import references a file/module that does not exist in the project, **remove or replace it** as appropriate.
    - Do **not**:
        - Add any new functionality unrelated to the correction.
        - Modify logic outside of the specified corrections.
        - Introduce any new features or classes beyond what's mentioned.
    - Maintain original indentation, code structure, and Django best practices.

    ---

    **Output Format**:
    - Return the corrected file content as raw Python code.
    - No markdown, no comments, no extra text.

    ---

    **Reminder**: Be conservative and minimal. Fix only what’s necessary to make the file **logically correct and semantically aligned with the metadata**.
    """

    response = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents=prompt
    )

    # Clean AI-generated code to remove markdown artifacts
    cleaned_content = clean_ai_generated_code(response.text)

    return cleaned_content

def dfs_feedback_loop(
    root: TreeNode,
    tree_structure: str,
    project_name: str,
    current_path: str = "",
    metadata_dict: dict = None,
    dependency_analyzer: DependencyAnalyzer = None,
    is_top_level: bool = True
):
    if root is None or metadata_dict is None:
        return
    
    project_files = get_project_files(metadata_dict=metadata_dict, project_name=project_name)

    clean_name = root.value.split('#')[0].strip()
    clean_name = clean_name.replace('(', '').replace(')', '')
    clean_name = clean_name.replace('uploads will go here, e.g., ', '')

    if is_top_level:
        full_path = os.path.join(project_name, clean_name)
    else:
        full_path = os.path.join(current_path, clean_name)

    if root.is_file:
        actual_dependencies = dependency_analyzer.get_dependencies(full_path) if dependency_analyzer else []
        file_metadata = next((entry for entry in metadata_dict[project_name] if entry["path"] == full_path), None)

        content = None
        
        try:
            if os.path.isfile(full_path):
                with open(full_path, 'r') as f:
                    content = f.read()
            else:
                print(f"Not a file: {full_path}")
                return
        except FileNotFoundError:
            print(f"File not found: {full_path}")
            return
        except Exception as e:
            print(f"Error reading file {full_path}: {e}")
            return

        if content is not None and file_metadata is not None:
            
            try:
                correctness, changes_needed = check_file_coupleness(
                    metadata_dict = file_metadata,
                    file_content=content,
                    file_path=full_path,
                    actual_dependencies=actual_dependencies
                )
            except Exception as e:
                print(f"Error checking file coupling for {full_path}: {e}")
                correctness = "undetermined"
                changes_needed = f"Could not analyze coupling due to error: {e}"

            all_validation_issues = comprehensive_file_validation(full_path, content, project_files)

            if correctness == "correct" or correctness == "undetermined":
                if all_validation_issues:
                    print(f"Validation issues found in {full_path}: {all_validation_issues}")
                    changes_needed += f" Validation issues: {all_validation_issues}"
                    correctness = "incorrect"
                elif correctness == "undetermined":
                    print(f"Could not determine correctness for {full_path}. Manual review needed. Changes needed: {changes_needed}")
                else:
                    print(f"No changes needed for {full_path}")
                    
            if correctness == "incorrect" or all_validation_issues:
                print(f"File {full_path} needs fixes. Changes needed: {changes_needed}")
                if all_validation_issues:
                    changes_needed += f"Validation issues found in {full_path}: {all_validation_issues}"
                    print(f"Validation issues found in {full_path}: {all_validation_issues}")
                
                try:
                    refined_content = refine_for_comprehensive_fixes(   
                        content,
                        changes_needed,
                        all_validation_issues
                    )
                    
                    if not refined_content or refined_content.strip() == "":
                        print(f"Warning: AI returned empty content for {full_path}, skipping update")
                        return
                    
                    validation_after_fix = comprehensive_file_validation(full_path, refined_content, project_files)
                    if validation_after_fix:
                        print(f"Warning: Refined content still has issues for {full_path}: {validation_after_fix}")
                        refined_content = refine_for_comprehensive_fixes(
                            refined_content,
                            f"Still has issues: {validation_after_fix}",
                            validation_after_fix
                        )
                    
                    with open(full_path, 'w') as f:
                        f.write(refined_content)

                    if dependency_analyzer:
                        dependency_analyzer.add_file(full_path, content=refined_content)
                    
                    if project_name in metadata_dict:
                        for entry in metadata_dict[project_name]:
                            if entry["path"] == full_path:
                                entry["description"] = refined_content
                                break
                    
                    print(f"✅ Updated file {full_path} based on feedback")
                except Exception as e:
                    print(f"Error updating file {full_path}: {e}")
                    print(f"Skipping file updates for {full_path} due to error")
 
    else:
        try:
            for child in root.children:
                dfs_feedback_loop(
                    root=child,
                    tree_structure=tree_structure,
                    project_name=project_name,
                    current_path=full_path,
                    metadata_dict=metadata_dict,
                    dependency_analyzer=dependency_analyzer,
                    is_top_level=False
                )
        except Exception as e:
            print(f"Error processing children of {full_path}: {e}")
            print("Continuing with remaining files...")

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

def extract_file_path_from_error(eo: str):
    prompt = f"""
    You are a Django error analyzer. Extract the exact file path from this Django error output.

    Error Output:
    {eo}

    Return ONLY the file path where the error occurred. If multiple files are mentioned, return the primary file causing the error.
    Return just the path, no explanation or markdown.
    
    Examples:
    - If error mentions "/home/user/project/app/models.py", return: /home/user/project/app/models.py
    - If error mentions "app.models", try to infer the likely path: app/models.py
    """

    resp = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents = prompt
    )

    return resp.text

def fix_django_error(file_path: str, eo: str, project_structure: str):
    try:
        with open(file_path, 'r') as f:
            file_content = f.read()
    except FileNotFoundError:
        print("File not found error")
        return None
    except Exception as e:
        print(f"The error is: {e}")
        return None
    
    prompt = f"""
    You are an expert Django developer. Fix the Django error in this file.

    **File Path**: {file_path}
    
    **Current File Content**:
    {file_content}

    **Error Output**:
    {eo}

    **Project Structure**:
    {project_structure}

    **Instructions**:
    1. Analyze the error and identify the root cause
    2. Fix ONLY the specific error mentioned
    3. Common Django error fixes:
       - Import errors: Remove or correct invalid imports
       - Model field errors: Fix field definitions
       - Migration errors: Correct model relationships
       - Syntax errors: Fix Python syntax issues
       - Missing dependencies: Add required imports from Django or project modules
    4. Do NOT add new functionality, only fix the error
    5. Maintain original code structure and Django best practices

    **Return only the corrected file content as raw code, no markdown or explanations.**
    """

    response = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents=prompt
    )

    cleaned_content = clean_ai_generated_code(response.text)

    return cleaned_content

def run_django_projects(command:list, project_path:str, max_retries:int = 15):
    for attempt in range(max_retries):
        try:
            print(f"Executing this command: {command}")

            res = subprocess.run(
                command,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=60
            )

            if(res.returncode == 0):
                print(f"command ran successfully, the command : {command}")
                return True, res.stdout
            else:
                print(f"Command failed, the command is {command}")
                print(f"THe error output is {res.stderr}")
                return False, res.stderr
        except Exception as e:
            print(f"This {e} exception occured")
            return False, str(e)
    
    return False, "Max retries exceeded, please increase if the error persists"

def resolve_django_errors(project_name: str, project_structure: str, max_iterations: int = 15):
    project_path = os.path.join(os.getcwd(), f"{project_name}/{project_name}")
    manage_py_path = os.path.join(project_path, "manage.py")

    if not os.path.exists(manage_py_path):
        print(f"manage.py not found in {project_path}. Cannot run Django commands.")
        return False
    
    print("1. running makemigrations")
    make_migrations_success = False

    for iteration in range(max_iterations):
        print(f"Makemigrations attempt {iteration + 1}/{max_iterations}")
        command = ["python", manage_py_path, "makemigrations"]
        success, output = run_django_projects(command, project_path)

        if not success:
            print(f"Error during makemigrations: {output}")
            
            error_file_path = extract_file_path_from_error(output)
            print("identified error file path is: ", error_file_path)

            if error_file_path:
                print(f"Fixing error in file: {error_file_path}")

                fixed_content = fix_django_error(
                    file_path=error_file_path,
                    eo=output,
                    project_structure=project_structure
                )

                if fixed_content:
                    try:
                        with open(error_file_path, 'w') as f:
                            f.write(fixed_content)
                        print(f"Fixed content written to {error_file_path}")
                    except Exception as e:
                        print(f"Error writing fixed content to {error_file_path}: {e}")
                else:
                    print(f"Could not fix the error in {error_file_path}. Manual intervention required.")

            else:
                print("No specific file path could be extracted from the error output. Manual intervention required.")
        
        else:
            print(f"✅ makemigrations successful on iteration {iteration + 1}")
            make_migrations_success = True
            break

    if not make_migrations_success:
        print("❌ makemigrations failed after maximum iterations. Please check the errors manually.")
        return False
    
    print("2. running migrate")
    success, output = run_django_projects(
        ["python", manage_py_path, "migrate"],
        project_path
    )

    if not success:
        print(f"Error during migrate: {output}")
        return False
    
    print("3. running runserver check to ensure no errors")
    check_success = False

    for iteration in range(max_iterations):
        print(f"Django check attempt {iteration + 1}/{max_iterations}")
        success, output = run_django_projects(
            ["python", manage_py_path, "check"],
            project_path
        )

        if success:
            print(f"✅ runserver check successful on iteration {iteration + 1}")
            check_success = True
            break

        else:
            print(f"Error during runserver check: {output}")
            
            error_file_path = extract_file_path_from_error(output)
            print("identified error file path is: ", error_file_path)

            if error_file_path and os.path.exists(error_file_path):
                print(f"Fixing error in file: {error_file_path}")

                fixed_content = fix_django_error(
                    file_path=error_file_path,
                    eo=output,
                    project_structure=project_structure
                )

                if fixed_content:
                    try:
                        with open(error_file_path, 'w') as f:
                            f.write(fixed_content)
                        print(f"Fixed content written to {error_file_path}")
                    except Exception as e:
                        print(f"Error writing fixed content to {error_file_path}: {e}")
                else:
                    print(f"Could not fix the error in {error_file_path}. Manual intervention required.")

            else:
                print("No specific file path could be extracted from the error output. Manual intervention required.")

    if check_success:
        print("\n🎉 All Django errors resolved successfully!")
        print(f"✅ Project {project_name} is ready to run!")
        print(f"🚀 You can now run: cd {project_name} && python manage.py runserver")
        return True
    else:
        print("\n❌ Failed to resolve all Django errors")
        return False

def extract_project_name(prompt: str) -> str:
    match = re.search(r'^Project\s+name\s*:\s*([a-zA-Z0-9_\-]+)', prompt, re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1)
    else:
        return "default_project_name"

prompt = """
Build a Transport Management System Web Application with the following modules and functionalities:

1. Master Module:
    Create a module to maintain details of unorganized transporters.
    When a new transporter is added:
    Auto-generate a unique login ID and password.
    These credentials should allow the transporter to log in to their portal.
2. Transporter Portal:
    Once logged in, the transporter should be able to:
    View all consignments assigned to them.
    Update consignment status (e.g., In Transit, Delivered, Delayed, No Status).
    Upload POD (Proof of Delivery) as an image.
    Enter delivery details, including delivery date and remarks.
3. Dashboard & Reporting (for Admin):
    A graphical dashboard showing:
        Total consignments
        Delivered
        In Transit
        No Status
    A count of consignments by status.
    For delivered consignments:
        Count how many were:
            Delivered on time
            1–3 days delayed
            4–6 days delayed
            More than 6 days delayed
        Count of delivered consignments with and without POD images.
    Provide the ability to:
        View, filter, and export detailed reports.
        Download data in Excel/PDF format.
"""
refined_prompt = refine_prompt(prompt)
print(refined_prompt)
project_name =extract_project_name(refined_prompt)

print(project_name)
response = generate_folder_struct(refined_prompt)
print(response)
folder_tree = generate_tree(response, project_name)
print(folder_tree.print_tree())
dependency_analyzer = DependencyAnalyzer()
json_file_name = "projects_metadata.json"
metadata_dict = {project_name: []}

output_dir = os.path.dirname(json_file_name)
if output_dir:
    os.makedirs(output_dir, exist_ok=True)

dfs_tree_and_gen(root=folder_tree, refined_prompt=refined_prompt, tree_structure=response, project_name=project_name, current_path="", parent_context="", json_file_name=json_file_name, metadata_dict=metadata_dict, dependency_analyzer=dependency_analyzer)

dependency_analyzer.visualize_graph()

for entry in metadata_dict[project_name]:
    path = entry["path"]
    entry["couples_with"] = dependency_analyzer.get_dependencies(entry["path"])

with open(json_file_name, 'w') as f:
    json.dump(metadata_dict, f, indent=4)

print("Starting feedback loop to validate and fix files...")
try:
    dfs_feedback_loop(folder_tree, response, project_name, current_path="", metadata_dict=metadata_dict, dependency_analyzer=dependency_analyzer, is_top_level=True)
    print("Feedback loop completed successfully!")
    
    print("Running final validation pass...")
    final_validation_issues = []
    project_files = get_project_files(metadata_dict, project_name)
    
    for entry in metadata_dict[project_name]:
        file_path = entry["path"]
        if file_path.endswith('.py'):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                issues = comprehensive_file_validation(file_path, content, project_files)
                if issues:
                    final_validation_issues.extend(issues)
                    print(f"⚠️ Final validation issues in {file_path}: {issues}")
            except Exception as e:
                print(f"Error reading {file_path} for final validation: {e}")
    
    if final_validation_issues:
        print(f"⚠️ Total final validation issues found: {len(final_validation_issues)}")
    else:
        print("✅ All files passed final validation!")
        
except Exception as e:
    print(f"Error during feedback loop: {e}")
    print("Continuing with Django error resolution...")

with open(json_file_name, 'w') as f:
    json.dump(metadata_dict, f, indent=4)

# res = subprocess.run(["python"])

django_success = resolve_django_errors(
    project_name=project_name,
    project_structure=response,
    max_iterations=25
)

if django_success:
    print(f"\n🎉 Project {project_name} is fully functional!")
else:
    print(f"\n⚠️ Project {project_name} may have remaining issues that need manual intervention.")


print("Happa... done, pothum da")
