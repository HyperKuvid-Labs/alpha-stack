import google.generativeai as genai
import string
import os 
import json
import re
from tqdm import tqdm
import networkx as nx
import ast 
from typing import List, Set
import toml

genai.configure(api_key="AIzaSyAb56f8gsiKgrg7ry3UWcuiDbGQsLMFJj0")

#this is still confidential, so i want you guys to not use in any of your projects yet.

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
    '.go', '.html', '.css', '.scss', '.sass', '.less', '.json', '.js', '.ts',
    '.md', '.yml', '.yaml', '.env', '.txt', '.png', '.ico', '.svg', '.jpg', 
    '.jpeg', '.webp', '.gif', '.sh', '.mod', '.sum', '.tmpl', '.tpl'
}
GENERATABLE_FILENAMES = {
    'main.go', 'go.mod', 'go.sum', 'Dockerfile', 'docker-compose.yml',
    'README.md', '.gitignore', '.env', '.env.example', 'Makefile',
    'config.yaml', 'config.json', '.air.toml', 'swagger.yaml', 'swagger.json'
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
        
        if file_path.endswith(".go"):
            import_statements = re.findall(r'import\s+(?:\([^)]*\)|"([^"]+)")', content)
            for imp in import_statements:
                if imp:
                    dependencies.add(imp)
            
            multi_import = re.findall(r'import\s+\(\s*([^)]+)\s*\)', content, re.DOTALL)
            for block in multi_import:
                imports = re.findall(r'"([^"]+)"', block)
                for imp in imports:
                    dependencies.add(imp)
            
            gin_routes = re.findall(r'\.(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\(\s*"([^"]+)"', content)
            for route in gin_routes:
                dependencies.add(f"route:{route}")
            
            template_usage = re.findall(r'\.HTML\s*\(\s*\d+\s*,\s*"([^"]+)"', content)
            for template in template_usage:
                dependencies.add(template)
            
            struct_usage = re.findall(r'([A-Z][a-zA-Z0-9]*)\s*{', content)
            for struct in struct_usage:
                dependencies.add(f"struct:{struct}")

        elif file_path.endswith((".mod", ".sum")):
            if file_path.endswith(".mod"):
                module_deps = re.findall(r'require\s+([^\s]+)', content)
                for dep in module_deps:
                    dependencies.add(dep)
                
                replace_deps = re.findall(r'replace\s+([^\s]+)', content)
                for dep in replace_deps:
                    dependencies.add(dep)

        elif file_path.endswith(".json"):
            try:
                json_data = json.loads(content)
                
                if 'dependencies' in json_data:
                    for dep_name in json_data['dependencies'].keys():
                        dependencies.add(dep_name)
                
                if 'devDependencies' in json_data:
                    for dep_name in json_data['devDependencies'].keys():
                        dependencies.add(dep_name)
                        
            except Exception as e:
                print(f"Error parsing JSON {file_path}: {e}")

        elif file_path.endswith((".css", ".scss", ".sass", ".less")):
            imports = re.findall(r'@import\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in imports:
                dependencies.add(imp)
            
            use_statements = re.findall(r'@use\s+[\'"]([^\'"]+)[\'"]', content)
            for use_stmt in use_statements:
                dependencies.add(use_stmt)

        elif file_path.endswith((".html", ".tmpl", ".tpl")):
            template_includes = re.findall(r'{{\s*template\s+"([^"]+)"', content)
            for template in template_includes:
                dependencies.add(template)
            
            partial_includes = re.findall(r'{{\s*partial\s+"([^"]+)"', content)
            for partial in partial_includes:
                dependencies.add(partial)
            
            scripts = re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', content)
            for script in scripts:
                dependencies.add(script)
            
            links = re.findall(r'<link[^>]+href=[\'"]([^\'"]+)[\'"]', content)
            for link in links:
                dependencies.add(link)

        elif file_path.endswith((".yml", ".yaml")):
            try:
                import yaml
                yaml_data = yaml.safe_load(content)
                
                if isinstance(yaml_data, dict):
                    if 'services' in yaml_data:
                        for service_name in yaml_data['services'].keys():
                            dependencies.add(f"service:{service_name}")
                    
                    if 'jobs' in yaml_data:
                        for job_name, job_config in yaml_data['jobs'].items():
                            if 'uses' in job_config:
                                dependencies.add(job_config['uses'])
                            if 'steps' in job_config:
                                for step in job_config['steps']:
                                    if isinstance(step, dict) and 'uses' in step:
                                        dependencies.add(step['uses'])
                                        
            except Exception as e:
                print(f"Error parsing YAML {file_path}: {e}")

        elif file_path.endswith(".js"):
            import_statements = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in import_statements:
                dependencies.add(imp)
            
            require_statements = re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', content)
            for req in require_statements:
                dependencies.add(req)

        elif file_path.endswith("Makefile"):
            target_deps = re.findall(r'^([a-zA-Z0-9_-]+):\s*([a-zA-Z0-9_\s-]*)', content, re.MULTILINE)
            for target, deps in target_deps:
                if deps.strip():
                    for dep in deps.split():
                        dependencies.add(f"make:{dep}")
        
        return dependencies
    
    def resolve_go_import(self, file_dir: str, import_path: str):
        if import_path.startswith('./') or import_path.startswith('../'):
            return os.path.join(file_dir, import_path)
        
        project_root = self.find_project_root(file_dir)
        if project_root:
            go_mod_path = os.path.join(project_root, 'go.mod')
            if os.path.exists(go_mod_path):
                with open(go_mod_path, 'r') as f:
                    mod_content = f.read()
                    module_match = re.search(r'module\s+([^\s]+)', mod_content)
                    if module_match:
                        module_name = module_match.group(1)
                        if import_path.startswith(module_name):
                            relative_path = import_path.replace(module_name, '').lstrip('/')
                            return os.path.join(project_root, relative_path)
        
        return import_path
    
    def find_project_root(self, current_dir: str):
        while current_dir != os.path.dirname(current_dir):
            if (os.path.exists(os.path.join(current_dir, 'go.mod')) or 
                os.path.exists(os.path.join(current_dir, 'main.go'))):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        return current_dir
    
    def get_dependencies(self, file_path: str) -> List[str]:
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        return list(self.graph.predecessors(file_path))
    
    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)
    
    def get_go_packages(self):
        packages = set()
        for node in self.graph.nodes:
            if node.endswith("go.mod"):
                for dep in self.get_dependencies(node):
                    if not dep.startswith('./') and not dep.endswith('.go'):
                        packages.add(dep)
        return packages
    
    def get_gin_routes(self):
        routes = set()
        for node in self.graph.nodes:
            if node.endswith(".go"):
                for dep in self.get_dependencies(node):
                    if dep.startswith('route:'):
                        routes.add(dep.replace('route:', ''))
        return routes
    
    def get_templates(self):
        templates = set()
        for node in self.graph.nodes:
            for dep in self.get_dependencies(node):
                if dep.endswith(('.html', '.tmpl', '.tpl')):
                    templates.add(dep)
        return templates
    
    def get_structs(self):
        structs = set()
        for node in self.graph.nodes:
            if node.endswith(".go"):
                for dep in self.get_dependencies(node):
                    if dep.startswith('struct:'):
                        structs.add(dep.replace('struct:', ''))
        return structs
    
    def visualize_graph(self):
        try:
            import matplotlib.pyplot as plt
            pos = nx.spring_layout(self.graph)
            
            node_colors = []
            for node in self.graph.nodes:
                if node.endswith('.go'):
                    node_colors.append('lightblue')
                elif node.endswith(('.html', '.tmpl', '.tpl')):
                    node_colors.append('lightgreen')
                elif node.endswith(('.css', '.scss')):
                    node_colors.append('lightcoral')
                elif node.endswith(('.mod', '.sum')):
                    node_colors.append('lightyellow')
                else:
                    node_colors.append('lightgray')
            
            nx.draw(self.graph, pos, with_labels=True, arrows=True, 
                   node_size=2000, node_color=node_colors, 
                   font_size=8, font_color='black', edge_color='gray')
            plt.title("Go Gin Dependency Graph")
            plt.show()
        except ImportError:
            print("Matplotlib is not installed. Skipping graph visualization.")


def refine_prompt(prompt: string) ->  string:
    resp = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents = f"""
            You are a senior Go + Gin architect. Your task is to take a high-level project idea and generate a detailed prompt that instructs a language model to output a production-ready Go + Gin application folder structure, including all directories and file names, but no file contents or code.

Analyse the {prompt} first—if it lacks clarity or scope, elaborate on it appropriately before proceeding. If the prompt is already detailed, return it as is.

project_name : {prompt}

Follow these rules when writing the refined prompt:
Prompt Template to Generate:
Project Name : 

Generate the folder structure only (no code or file contents) for a Go + Gin project named .

This project is a , with the following key features:





Use Go + Gin best practices:

Modular, reusable package structure with clear separation of concerns.

Strictly include go.mod in the root directory to manage dependencies.

Follow the standard Go project layout for production-grade applications.

Include standard folders and files for:

Handlers: handlers/

Models: models/

Services: services/

Middleware: middleware/

Routes: routes/

Database: database/

Configuration: config/

Static assets: static/

Templates: templates/

Main entry point: main.go

The application modules should include, but are not limited to:

handlers – HTTP request handlers with proper organization.

models – data structures and database models.

services – business logic and service layer.

middleware – HTTP middleware and authentication guards.

routes – route definitions and API endpoints.

Follow Go and Gin naming conventions and proper project structuring.

Return only the folder structure with relevant file names in a tree view format.
Do not include any code or file contents.

Additional Technical Requirements & Best Practices:
Maintain modularity and reusability across all Go packages.

Use a standard Go project layout:

Root project directory with go.mod and main.go

Handlers directory for HTTP request handling

Models directory for data structures

Services directory for business logic

Database directory for database connections and migrations

Config directory for application configuration

Static directory for static assets

Templates directory for HTML templates

Include go.mod, go.sum, .env.example, .env, README.md, .gitignore

Placeholders for deployment: Dockerfile, docker-compose.yml, .github/workflows/, etc.

Each package should follow Go conventions with proper organization

The application should support JSON APIs and HTML template rendering

📌 Backend Development Guidelines:
Use Go modules for dependency management. All logic must reside in properly structured .go files organized under appropriate packages.

Leverage Gin framework with proper middleware architecture. Include HTTP handlers with clear separation of concerns and proper request/response handling.

Use structured logging and error handling throughout the application. Organize custom middleware and utilities in dedicated packages.

Ensure proper API design, database integration, and performance optimization through Go's built-in features and Gin's middleware system.

Example Input:
Input: e-commerce marketplace

Expected Refined Prompt Output:
Project Name : ecommerce_marketplace

Generate the folder structure only (no code or file contents) for a Go + Gin project named ecommerce_marketplace.

The project is an E-commerce Marketplace with the following key features:

Users can browse products, add items to cart, and complete purchases.

Vendors can register, manage product listings, and track sales.

Administrators can manage users, moderate listings, and oversee platform operations.

Real-time inventory tracking and order management.

User Roles and Capabilities:

Customers: Browse products, manage cart, place orders, and track shipments.

Vendors: Manage product catalog, process orders, and view analytics.

Admins: Platform management, user moderation, and system configuration.

Use Go + Gin best practices:

Structure the project with modular Go package architecture.

Implement RESTful API endpoints with Gin routes.

Use Go modules for dependency management with proper versioning.

Implement proper database integration and business logic separation.

Follow standard Go project layout with clear package boundaries.

Include folders for:

handlers/

models/

services/

middleware/

routes/

database/

Application modules to include:

handlers

models

services

middleware

routes

config

Include standard Go files such as:

go.mod and main.go in the root

Handler files in handlers/ package

Model definitions in models/ package

API routes in routes/ package

Service logic in services/ package

Return only the complete end-to-end folder structure in a tree view format. Do not include any file content or code.
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

def generate_folder_struct(prompt: string) -> string:
    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents = prompt
    )

    return resp.text

def generate_file_metadata(context: str, filepath: str, refined_prompt: str, tree: str, json_file_name: str, file_content: str) -> str:
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)

    prompt = f"""You are analyzing a file from a Go + Gin project. Generate a detailed yet concise metadata description that captures its purpose, structure, and relationships.

File Information

File Name: {filename}

File Type: {file_type} (e.g., .go, .mod, .sum, .json, .yaml, .html, .css)

Project Location: {context} (e.g., handlers/, models/, services/, middleware/, routes/, config/, templates/)

Project Idea: {refined_prompt}

Project Structure:
{tree}

File Content:
{file_content}

What to include in your response:

A concise 2–3 sentence summary of what this file does and how it fits into the Go + Gin project.

If it's a Go file (.go):

Mention key structs, functions, interfaces, packages imported, and HTTP handlers or business logic implemented.

If it's a module file (.mod/.sum):

Describe the dependencies, module name, and Go version requirements it manages.

If it's a configuration file (.json/.yaml):

Explain the application settings, database configuration, or deployment configuration it manages.

If it's a template file (.html/.tmpl):

Describe the HTML structure, template variables, and rendering context it provides.

If it's a styling file (.css/.scss):

Describe the styling approach, component styles, or global styles it provides.

List which other files or packages this file is directly coupled with, either through imports, struct usage, or function dependencies.

Mention any external packages, Go standard library, or third-party libraries (e.g., gin-gonic/gin, gorm.io/gorm, github.com/joho/godotenv) used here.

Response Format:

Return only the raw description text (no markdown, bullets, or headings).

Do not include any code or formatting artifacts.
    """

    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents = prompt
    )

    return resp.text

def generate_file_content(context: str, filepath: str, refined_prompt: str, tree: str, json_file_name: str) -> str:
    
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)
    
    prompt = f"""Generate the content of a Go + Gin project file.

Details:

File Name: {filename}

File Type: {file_type} (e.g., Go, Mod, Sum, JSON, YAML, HTML, CSS, Template)

Project Context: {context} (e.g., handlers/, models/, services/, middleware/, routes/, config/, templates/, static/)

Project Idea: {refined_prompt}

Full Folder Structure: {tree}

Requirements:

Follow Go + Gin best practices relevant to the file type

Include only necessary imports or dependencies

Use documentation comments and inline comments for clarity where applicable

For Go files (.go):
Use proper Go conventions with clear package declarations

Include comprehensive struct definitions and method documentation

Add Go doc comments for exported functions and types

Follow Go naming conventions and project structure

Implement proper error handling and logging

Use Gin framework features and middleware appropriately

For Module files (.mod/.sum):
Use proper Go module versioning and dependency management

Include all necessary dependencies with appropriate versions

Configure proper module name and Go version requirements

Set up indirect dependencies and version constraints

Follow Go modules best practices for dependency resolution

For Configuration files (.json/.yaml):
Include all necessary application settings and parameters

Configure proper database connections and environment variables

Set up logging, security, and performance configurations

Configure deployment and runtime environment settings

Set up development and production environment separation

For Template files (.html/.tmpl):
Write clean, semantic HTML with proper Go template syntax

Use Go template functions and pipeline operations correctly

Include proper template inheritance and partial rendering

Implement proper data binding and context usage

Follow HTML5 standards and accessibility guidelines

For Styling files (.css/.scss):
Write modular, reusable styles with proper organization

Follow modern CSS practices and naming conventions

Ensure responsive design and cross-browser compatibility

Use CSS custom properties and modern features

Implement proper component scoping and global styles

For Handler files:
Write clean, RESTful API handlers with proper validation

Use Gin context and middleware appropriately

Include comprehensive error handling and HTTP status codes

Add proper request/response serialization

Follow REST API design principles and conventions

Output:

Return only the raw code as it would appear in the file (no markdown or extra formatting)
    """
    
    response = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents=prompt
    )

    # metadata = generate_file_metadata(context, filepath, refined_prompt, tree, json_file_name, response.text)
    
    return response.text

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
    You are an expert Go + Gin code reviewer.

You are reviewing the coupling accuracy of a Go + Gin file by comparing:

The actual imports, dependencies, and logical usage in the file.

The declared couples_with list in the project's metadata.

The dependencies extracted via static analysis.

Your goal is to verify whether the declared couplings are complete, precise, and consistent with the file's true behavior.

File Path: {file_path}

File Content:
{file_content}

Declared Metadata Couplings (couples_with):
{metadata_dict.get('couples_with', [])}

Statically Detected Dependencies (from code analysis):
{actual_dependencies}

Instructions:

Analyze the file's actual import statements, package usage, struct references, and cross-module dependencies.

For Go files: Check import statements, struct usage, function calls, and package dependencies.

For Module files: Check require statements, replace directives, and version constraints.

For Configuration files: Check dependency declarations, service configurations, and build settings.

For Template files: Check template includes, partial references, and asset dependencies.

For Styling files: Check @import statements, CSS custom properties, and component style dependencies.

Compare that to the declared couplings in the metadata (couples_with).

Then compare both with the dependencies inferred via static analysis (actual_dependencies).

If you find discrepancies, please describe the issue and suggest corrections.

Determine if:

All couplings in the code are properly captured in the metadata.

There are any incorrect, missing, or extra entries in the metadata.

Any syntactical or logical errors in the file that prevent it from compiling or running correctly.

Return ONLY this exact JSON format:
{{
"correctness": "correct" or "incorrect",
"changes_needed": "clear explanation of what's missing, extra, or incorrect (empty string if everything is accurate)"
}}

Examples:

Example 1 (Correct):
{{
"correctness": "correct",
"changes_needed": ""
}}

Example 2 (Incorrect):
{{
"correctness": "incorrect",
"changes_needed": "The file imports github.com/gin-gonic/gin but gin-gonic/gin is missing in the declared metadata. Also, metadata lists gorm.io/gorm but it should be gorm.io/driver/postgres as the actual import. The file also uses User struct from models package but models/user.go is not captured in the metadata."
}}
    """
    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents = prompt
    )


    # resp = """
    #     ```json
    # {
    # "correctness": "correct",
    # "changes_needed": ""
    # }
    # ```"""

    cleaned_response = resp.text.strip('`').replace('json\n', '').strip()
    # data = json.loads(cleaned_response)
    try:
        data = json.loads(cleaned_response)
        correctness = data["correctness"]
        changes_needed = data["changes_needed"]
        return correctness, changes_needed
    except json.JSONDecodeError:
        return "undetermined", f"Could not parse response: {resp.text}. Please check the model's output format."
    

def validate_imports_exist(file_path: str, content: str, project_files: set):
    invalid_imports = []
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.go':
        import_pattern = r'import\s+(?:\([^)]*\)|"([^"]+)")'
        multi_import_pattern = r'import\s+\(\s*([^)]+)\s*\)'
        struct_pattern = r'([A-Z][a-zA-Z0-9]*)\s*{'
        interface_pattern = r'type\s+([A-Z][a-zA-Z0-9]*)\s+interface'
        
        import_matches = re.findall(import_pattern, content)
        multi_import_matches = re.findall(multi_import_pattern, content, re.DOTALL)
        struct_matches = re.findall(struct_pattern, content)
        interface_matches = re.findall(interface_pattern, content)
        
        all_imports = []
        for imp in import_matches:
            if imp:
                all_imports.append(imp)
        
        for block in multi_import_matches:
            imports = re.findall(r'"([^"]+)"', block)
            all_imports.extend(imports)
        
        for imp in all_imports:
            if imp.startswith('./') or imp.startswith('../'):
                file_dir = os.path.dirname(file_path)
                resolved_path = os.path.normpath(os.path.join(file_dir, imp))
                
                potential_files = [
                    resolved_path,
                    resolved_path + '.go',
                    os.path.join(resolved_path, 'main.go'),
                    os.path.join(resolved_path, 'handler.go'),
                    os.path.join(resolved_path, 'model.go'),
                    os.path.join(resolved_path, 'service.go')
                ]
                
                if not any(pf in project_files for pf in potential_files):
                    invalid_imports.append(f"Local import '{imp}' in {file_path} does not exist")
            
            elif not any(imp.startswith(external) for external in [
                'fmt', 'log', 'net/http', 'os', 'strconv', 'time', 'context', 'database/sql',
                'github.com/gin-gonic/gin', 'gorm.io/', 'github.com/'
            ]):
                go_mod_path = 'go.mod'
                if go_mod_path in project_files:
                    try:
                        with open(go_mod_path, 'r') as f:
                            mod_content = f.read()
                        if imp not in mod_content:
                            invalid_imports.append(f"Go package '{imp}' not found in go.mod dependencies")
                    except:
                        pass
        
        for struct in struct_matches:
            struct_files = [
                f"models/{struct.lower()}.go",
                f"models/model.go",
                f"handlers/{struct.lower()}.go"
            ]
            if not any(sf in project_files for sf in struct_files):
                invalid_imports.append(f"Struct '{struct}' in {file_path} may not exist in expected locations")
    
    elif file_ext == '.mod':
        require_pattern = r'require\s+([^\s]+)'
        replace_pattern = r'replace\s+([^\s]+)'
        
        require_matches = re.findall(require_pattern, content)
        replace_matches = re.findall(replace_pattern, content)
        
        for req in require_matches:
            if req.startswith('./') or req.startswith('../'):
                file_dir = os.path.dirname(file_path)
                resolved_path = os.path.normpath(os.path.join(file_dir, req))
                mod_file = os.path.join(resolved_path, 'go.mod')
                if mod_file not in project_files:
                    invalid_imports.append(f"Local module '{req}' does not contain go.mod")
    
    elif file_ext == '.json':
        if 'package.json' in file_path:
            try:
                json_data = json.loads(content)
                
                if 'dependencies' in json_data:
                    for dep_name in json_data['dependencies'].keys():
                        if dep_name.startswith('file:'):
                            file_path_dep = dep_name.replace('file:', '')
                            if file_path_dep not in project_files:
                                invalid_imports.append(f"Local file dependency '{file_path_dep}' does not exist")
                                
            except Exception:
                pass
    
    elif file_ext in ['.html', '.tmpl', '.tpl']:
        template_pattern = r'{{\s*template\s+"([^"]+)"'
        partial_pattern = r'{{\s*partial\s+"([^"]+)"'
        script_pattern = r'<script[^>]+src=[\'"]([^\'"]+)[\'"]'
        link_pattern = r'<link[^>]+href=[\'"]([^\'"]+)[\'"]'
        
        template_matches = re.findall(template_pattern, content)
        partial_matches = re.findall(partial_pattern, content)
        script_matches = re.findall(script_pattern, content)
        link_matches = re.findall(link_pattern, content)
        
        for template in template_matches:
            template_paths = [
                f"templates/{template}",
                f"templates/{template}.html",
                f"templates/{template}.tmpl"
            ]
            if not any(tp in project_files for tp in template_paths):
                invalid_imports.append(f"Template '{template}' in {file_path} does not exist")
        
        for partial in partial_matches:
            partial_paths = [
                f"templates/partials/{partial}",
                f"templates/{partial}",
                f"templates/partials/{partial}.html"
            ]
            if not any(pp in project_files for pp in partial_paths):
                invalid_imports.append(f"Partial '{partial}' in {file_path} does not exist")
        
        for script_src in script_matches:
            if not script_src.startswith('http') and not script_src.startswith('//'):
                if script_src.startswith('/'):
                    static_path = 'static' + script_src
                    if static_path not in project_files:
                        invalid_imports.append(f"Script source '{script_src}' in {file_path} does not exist in static folder")
                elif script_src not in project_files:
                    invalid_imports.append(f"Script source '{script_src}' in {file_path} does not exist")
        
        for link_href in link_matches:
            if not link_href.startswith('http') and not link_href.startswith('//'):
                if link_href.startswith('/'):
                    static_path = 'static' + link_href
                    if static_path not in project_files:
                        invalid_imports.append(f"Link href '{link_href}' in {file_path} does not exist in static folder")
                elif link_href not in project_files:
                    invalid_imports.append(f"Link href '{link_href}' in {file_path} does not exist")
    
    elif file_ext in ['.css', '.scss', '.sass', '.less']:
        import_pattern = r'@import\s+[\'"]([^\'"]+)[\'"]'
        use_pattern = r'@use\s+[\'"]([^\'"]+)[\'"]'
        url_pattern = r'url\([\'"]?([^\'"]+)[\'"]?\)'
        
        import_matches = re.findall(import_pattern, content)
        use_matches = re.findall(use_pattern, content)
        url_matches = re.findall(url_pattern, content)
        
        all_style_imports = import_matches + use_matches
        
        for style_import in all_style_imports:
            if style_import.startswith('./') or style_import.startswith('../'):
                file_dir = os.path.dirname(file_path)
                resolved_path = os.path.normpath(os.path.join(file_dir, style_import))
                
                potential_files = [
                    resolved_path,
                    resolved_path + '.css',
                    resolved_path + '.scss',
                    resolved_path + '.sass',
                    resolved_path + '.less'
                ]
                
                if not any(pf in project_files for pf in potential_files):
                    invalid_imports.append(f"Style import '{style_import}' in {file_path} does not exist")
        
        for url_ref in url_matches:
            if not url_ref.startswith('http') and not url_ref.startswith('data:') and not url_ref.startswith('//'):
                if url_ref.startswith('/'):
                    static_path = 'static' + url_ref
                    if static_path not in project_files:
                        invalid_imports.append(f"CSS URL reference '{url_ref}' in {file_path} does not exist in static folder")
                elif url_ref not in project_files:
                    invalid_imports.append(f"CSS URL reference '{url_ref}' in {file_path} does not exist")
    
    elif file_ext in ['.yml', '.yaml']:
        try:
            import yaml
            yaml_data = yaml.safe_load(content)
            
            if isinstance(yaml_data, dict):
                if 'services' in yaml_data:
                    for service_name, service_config in yaml_data['services'].items():
                        if 'build' in service_config and isinstance(service_config['build'], str):
                            dockerfile_path = os.path.join(service_config['build'], 'Dockerfile')
                            if dockerfile_path not in project_files:
                                invalid_imports.append(f"Dockerfile for service '{service_name}' does not exist at '{dockerfile_path}'")
                        
                        if 'volumes' in service_config:
                            for volume in service_config['volumes']:
                                if ':' in volume:
                                    host_path = volume.split(':')[0]
                                    if not host_path.startswith('/') and host_path not in project_files:
                                        invalid_imports.append(f"Volume path '{host_path}' for service '{service_name}' does not exist")
                
                if 'jobs' in yaml_data:
                    for job_name, job_config in yaml_data['jobs'].items():
                        if 'uses' in job_config:
                            action_ref = job_config['uses']
                            if action_ref.startswith('./'):
                                action_path = action_ref.replace('./', '')
                                if action_path not in project_files:
                                    invalid_imports.append(f"GitHub Action '{action_ref}' does not exist")
                        
                        if 'steps' in job_config:
                            for step in job_config['steps']:
                                if isinstance(step, dict) and 'uses' in step:
                                    action_ref = step['uses']
                                    if action_ref.startswith('./'):
                                        action_path = action_ref.replace('./', '')
                                        if action_path not in project_files:
                                            invalid_imports.append(f"GitHub Action step '{action_ref}' does not exist")
                                            
        except Exception:
            pass
    
    elif file_path == 'Dockerfile':
        copy_pattern = r'COPY\s+([^\s]+)'
        add_pattern = r'ADD\s+([^\s]+)'
        
        copy_matches = re.findall(copy_pattern, content)
        add_matches = re.findall(add_pattern, content)
        
        for copy_src in copy_matches:
            if not copy_src.startswith('http') and copy_src != '.':
                if copy_src not in project_files:
                    invalid_imports.append(f"COPY source '{copy_src}' in Dockerfile does not exist")
        
        for add_src in add_matches:
            if not add_src.startswith('http') and add_src != '.':
                if add_src not in project_files:
                    invalid_imports.append(f"ADD source '{add_src}' in Dockerfile does not exist")
    
    elif file_path == 'Makefile':
        include_pattern = r'include\s+([^\s]+)'
        
        include_matches = re.findall(include_pattern, content)
        
        for include_file in include_matches:
            if include_file not in project_files:
                invalid_imports.append(f"Makefile include '{include_file}' does not exist")
    
    return invalid_imports

def get_project_files(metadata_dict, project_name) -> set:
    project_files = set()
    for entry in metadata_dict.get(project_name, []):
        if entry["path"].endswith('.py'):
            rel_path = os.path.relpath(entry["path"], project_name)
            project_files.add(rel_path)
    return project_files
                                               
def refine_for_the_change_in_file(file_content, changes_needed):
    prompt = f"""
    You are an expert Go + Gin developer.

Your task is to correct the following Go + Gin project file so that its imports, dependencies, and references properly match the declared couplings and dependency expectations, based on feedback from a static analysis and metadata validation.

Original File Content:
{file_content}

Correction Feedback:
{changes_needed}

Requirements:

Fix only the issues mentioned in the Correction Feedback — including:

Missing or incorrect import statements and package references.

Imports of non-existent packages, handlers, models, or services — these should be removed.

Typographical errors in import statements, package names, or function names.

Syntactical errors in the file that prevent it from compiling correctly.

Missing package dependencies in go.mod files.

Incorrect struct references or function usage.

Missing or incorrect Go standard library imports.

Ensure that all imports and references are logically correct and semantically aligned with the metadata.

If an import statement is missing, add it.

If an import statement is incorrect, correct it.

If an import statement is redundant or not used, remove it.

If an import references a package/module that does not exist in the project, remove or replace it as appropriate.

For Go files, ensure proper package imports and struct usage.

For Module files, ensure proper dependency declarations and versions.

For Configuration files, ensure proper service configurations and settings.

For Template files, ensure proper template syntax and asset references.

Do not:

Add any new functionality unrelated to the correction.

Modify logic outside of the specified corrections.

Introduce any new handlers, models, or services beyond what's mentioned.

Maintain original indentation, code structure, and Go + Gin best practices.

Output Format:

Return the corrected file content as raw code (Go, Mod, YAML, JSON, HTML, etc.).

No markdown, no comments, no extra text.

Reminder: Be conservative and minimal. Fix only what's necessary to make the file logically correct and semantically aligned with the metadata.
    """

    response = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents=prompt
    )

    return response.text

def dfs_feedback_loop(
    root: TreeNode,
    tree_structure: str,
    project_name: str,
    current_path: str = "",
    metadata_dict: dict = None,
    dependency_analyzer: DependencyAnalyzer = None,
    is_top_level: bool = True
):
    """
    Traverse the tree and check file contents against metadata
    """
    if root is None or metadata_dict is None:
        return
    
    project_files = get_project_files(metadata_dict=metadata_dict, project_name=project_name)

    clean_name = root.value.split('#')[0].strip()
    clean_name = clean_name.replace('(', '').replace(')', '')
    clean_name = clean_name.replace('uploads will go here, e.g., ', '')

    # Build the full path
    if is_top_level:
        full_path = os.path.join(project_name, clean_name)
    else:
        full_path = os.path.join(current_path, clean_name)

    if root.is_file:
        # Initialize content as None
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
            
            correctness, changes_needed = check_file_coupleness(
                metadata_dict = file_metadata,
                file_content=content,
                file_path=full_path,
                actual_dependencies=actual_dependencies
            )

            invalid_imports = validate_imports_exist(file_path=full_path, content=content, project_files=project_files)

            if correctness == "correct" or correctness == "undetermined":
                if(correctness == "undetermined"):
                    print(f"Could not determine correctness for {full_path}. Manual review needed. Changes needed: {changes_needed}")
                else:
                    print(f"No changes needed for {full_path}")
            elif correctness == "incorrect":
                print(f"File {full_path} is incorrect. Changes needed: {changes_needed}")
                if invalid_imports:
                    changes_needed += f"Invalid imports found in {full_path}: {invalid_imports}"
                    print(f"Invalid imports found in {full_path}: {invalid_imports}")
                refined_content = refine_for_the_change_in_file(   
                    content,
                    changes_needed
                )
                try:
                    with open(full_path, 'w') as f:
                        f.write(refined_content)

                    if dependency_analyzer:
                        dependency_analyzer.add_file(full_path, content=refined_content)
                    
                    if project_name in metadata_dict:
                        for entry in metadata_dict[project_name]:
                            if entry["path"] == full_path:
                                entry["description"] = refined_content
                                break
                    
                    print(f"Updated file {full_path} based on feedback - {changes_needed}")
                except Exception as e:
                    print(f"Error updating file {full_path}: {e}")
 
    else:
        for child in root.children:
            dfs_feedback_loop(
                root=child,
                tree_structure=tree_structure,
                project_name=project_name,
                current_path=full_path,
                metadata_dict=metadata_dict,
                is_top_level=False
            )

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


def extract_project_name(prompt: str) -> str:
    match = re.search(r'^Project\s+name\s*:\s*([a-zA-Z0-9_\-]+)', prompt, re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1)
    else:
        return "default_project_name"


import sys

def main():
    if len(sys.argv) != 3:
        print("Usage: python alphamern.py <output_dir> <prompt_file>")
        sys.exit(1)
    
    output_dir = sys.argv[1]
    prompt_file = sys.argv[2]
    
    with open(prompt_file, 'r') as f:
        prompt = f.read()
        
    # prompt = sys.argv[1]
    refined_prompt = refine_prompt(prompt)
    project_name =extract_project_name(refined_prompt)
    print(project_name)
    response = generate_folder_struct(refined_prompt)
    print(response)
    folder_tree = generate_tree(response, project_name)
    print(folder_tree.print_tree())
    dependency_analyzer = DependencyAnalyzer()
    json_file_name = "projects_metadata.json"
    metadata_dict = {project_name: []}

    # output_dir = os.path.dirname(json_file_name)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    dfs_tree_and_gen(root=folder_tree, refined_prompt=refined_prompt, tree_structure=response, project_name=output_dir, current_path="", parent_context="", json_file_name=json_file_name, metadata_dict=metadata_dict, dependency_analyzer=dependency_analyzer)

    dependency_analyzer.visualize_graph()

    for entry in metadata_dict[project_name]:
        path = entry["path"]
        entry["couples_with"] = dependency_analyzer.get_dependencies(entry["path"])

    with open(json_file_name, 'w') as f:
        json.dump(metadata_dict, f, indent=4)


    dfs_feedback_loop(folder_tree, response, project_name, current_path="", metadata_dict=metadata_dict, dependency_analyzer=dependency_analyzer, is_top_level=True)

    with open(json_file_name, 'w') as f:
        json.dump(metadata_dict, f, indent=4)

    print("Happa... done, pothum da")
    
if __name__ == "__main__":
    main()
