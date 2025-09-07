
import google.generativeai as genai
import string
import os 
import json
import re
from tqdm import tqdm
import networkx as nx
import ast 
from typing import List, Set

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
    '.js', '.jsx', '.ts', '.tsx', '.json', '.html', '.css', '.scss', '.sass', 
    '.md', '.yml', '.yaml', '.env', '.txt', '.png', '.ico', '.svg', '.sh'
}

GENERATABLE_FILENAMES = {
    'Dockerfile', 
    'README.md', 
    '.gitignore', 
    'package.json',
    'package-lock.json',
    'yarn.lock',
    'docker-compose.yml', 
    '.env',
    '.env.local',
    '.env.development',
    '.env.production',
    'tsconfig.json',
    'next.config.js',
    'vite.config.js',
    'webpack.config.js',
    '.babelrc',
    '.eslintrc.js',
    '.prettierrc'
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

class DepenedencyAnalyzer:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.package_json_cache = {}
        self.node_modules_cache = {}
        self.typescript_config = {}
        
    def add_file(self, file_path: str, content: str):
        self.graph.add_node(file_path)
        dependencies = self.extract_dependencies(file_path, content)
        for dep in dependencies:
            self.graph.add_edge(file_path, dep)
    
    def extract_dependencies(self, file_path: str, content: str) -> Set[str]:
        dependencies = set()
        file_dir = os.path.dirname(file_path)
        
        if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
            es6_imports = re.findall(r'import\s+(?:[^;]+\s+from\s+)?["\']([^"\']+)["\']', content)
            for imp in es6_imports:
                resolved = self.resolve_js_import(file_dir, imp, file_path)
                if resolved:
                    dependencies.add(resolved)
            
            requires = re.findall(r'require\(["\']([^"\']+)["\']\)', content)
            for req in requires:
                resolved = self.resolve_js_import(file_dir, req, file_path)
                if resolved:
                    dependencies.add(resolved)
            
            dynamic_imports = re.findall(r'import\(["\']([^"\']+)["\']\)', content)
            for imp in dynamic_imports:
                resolved = self.resolve_js_import(file_dir, imp, file_path)
                if resolved:
                    dependencies.add(resolved)
            
            if file_path.endswith(('.jsx', '.tsx')):
                component_usage = re.findall(r'<([A-Z][a-zA-Z0-9]*)', content)
                for component in component_usage:
                    component_import = re.search(rf'import\s+.*{component}.*from\s+["\']([^"\']+)["\']', content)
                    if component_import:
                        resolved = self.resolve_js_import(file_dir, component_import.group(1), file_path)
                        if resolved:
                            dependencies.add(resolved)

        elif file_path.endswith('package.json'):
            try:
                data = json.loads(content)
                self.package_json_cache[file_path] = data
                
                for dep_type in ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies']:
                    if dep_type in data:
                        for dep_name in data[dep_type].keys():
                            dependencies.add(f"node_modules/{dep_name}")
                
                if 'scripts' in data:
                    for script_content in data['scripts'].values():
                        file_refs = re.findall(r'["\']([^"\']*\.[a-zA-Z]+)["\']', script_content)
                        for ref in file_refs:
                            if os.path.exists(os.path.join(file_dir, ref)):
                                dependencies.add(os.path.join(file_dir, ref))
                        
            except json.JSONDecodeError as e:
                print(f"Error parsing package.json {file_path}: {e}")

        elif file_path.endswith(('tsconfig.json', 'jsconfig.json')):
            try:
                data = json.loads(content)
                self.typescript_config[file_path] = data
                
                if 'compilerOptions' in data:
                    compiler_opts = data['compilerOptions']
                    
                    if 'baseUrl' in compiler_opts:
                        base_url = compiler_opts['baseUrl']
                        dependencies.add(os.path.join(file_dir, base_url))
                    
                    if 'paths' in compiler_opts:
                        for path_pattern, path_list in compiler_opts['paths'].items():
                            for path_item in path_list:
                                resolved_path = os.path.join(file_dir, path_item)
                                if os.path.exists(resolved_path):
                                    dependencies.add(resolved_path)
                
                if 'references' in data:
                    for ref in data['references']:
                        if 'path' in ref:
                            ref_path = os.path.join(file_dir, ref['path'])
                            dependencies.add(ref_path)
                            
            except json.JSONDecodeError as e:
                print(f"Error parsing TypeScript config {file_path}: {e}")

        elif file_path.endswith(('.css', '.scss', '.sass')):
            css_imports = re.findall(r'@import\s+["\']([^"\']+)["\']', content)
            for imp in css_imports:
                resolved = self.resolve_css_import(file_dir, imp)
                if resolved:
                    dependencies.add(resolved)
            
            scss_imports = re.findall(r'@import\s+["\']([^"\']+)["\']', content)
            for imp in scss_imports:
                for prefix in ['', '_']:
                    for ext in ['.scss', '.sass', '.css']:
                        potential_path = os.path.join(file_dir, f"{prefix}{imp}{ext}")
                        if os.path.exists(potential_path):
                            dependencies.add(potential_path)
                            break

        elif file_path.endswith('.html'):
            scripts = re.findall(r'<script\s+[^>]*src=["\']([^"\']+)["\']', content)
            for src in scripts:
                if not src.startswith(('http://', 'https://', '//')):
                    resolved_path = os.path.join(file_dir, src)
                    if os.path.exists(resolved_path):
                        dependencies.add(resolved_path)
            
            links = re.findall(r'<link\s+[^>]*href=["\']([^"\']+)["\']', content)
            for href in links:
                if not href.startswith(('http://', 'https://', '//')):
                    resolved_path = os.path.join(file_dir, href)
                    if os.path.exists(resolved_path):
                        dependencies.add(resolved_path)

        elif file_path.endswith(('.env', '.env.local', '.env.production', '.env.development')):
            file_refs = re.findall(r'=([^=\n]*\.[a-zA-Z]+)', content)
            for ref in file_refs:
                ref = ref.strip()
                if os.path.exists(os.path.join(file_dir, ref)):
                    dependencies.add(os.path.join(file_dir, ref))

        elif file_path.endswith(('.config.js', '.config.ts', 'webpack.config.js', 'vite.config.js', 'next.config.js')):
            file_refs = re.findall(r'["\']([^"\']*\.[a-zA-Z]+)["\']', content)
            for ref in file_refs:
                if not ref.startswith(('http://', 'https://')):
                    resolved_path = os.path.join(file_dir, ref)
                    if os.path.exists(resolved_path):
                        dependencies.add(resolved_path)

        return dependencies
    
    def resolve_js_import(self, file_dir: str, import_path: str, current_file: str):
        if not import_path.startswith('.'):
            node_modules_path = self.find_node_modules(file_dir, import_path)
            if node_modules_path:
                return node_modules_path
            return f"node_modules/{import_path}"
        
        base_path = os.path.join(file_dir, import_path)
        
        extensions = ['.js', '.jsx', '.ts', '.tsx', '.json']
        
        for ext in extensions:
            if os.path.exists(f"{base_path}{ext}"):
                return f"{base_path}{ext}"
        
        if os.path.isdir(base_path):
            for ext in extensions:
                index_path = os.path.join(base_path, f"index{ext}")
                if os.path.exists(index_path):
                    return index_path
        
        return None
    
    def resolve_css_import(self, file_dir: str, import_path: str) :
        if import_path.startswith('~'):
            return f"node_modules/{import_path[1:]}"
        
        base_path = os.path.join(file_dir, import_path)
        
        extensions = ['', '.css', '.scss', '.sass']
        
        for ext in extensions:
            full_path = f"{base_path}{ext}"
            if os.path.exists(full_path):
                return full_path
        
        return None
    
    def find_node_modules(self, start_dir: str, package_name: str):
        current_dir = start_dir
        
        while current_dir != os.path.dirname(current_dir):
            node_modules_path = os.path.join(current_dir, 'node_modules', package_name)
            if os.path.exists(node_modules_path):
                return node_modules_path
            current_dir = os.path.dirname(current_dir)
        
        return None
    
    def get_dependencies(self, file_path: str) -> List[str]:
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        return list(self.graph.predecessors(file_path))
    
    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)
    
    def find_circular_dependencies(self):
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except Exception as e:
            print(f"Error finding cycles: {e}")
            return []
    
    def get_dependency_depth(self, file_path: str) :
        def depth(node, visited):
            if node in visited:
                return 0
            visited.add(node)
            successors = list(self.graph.successors(node))
            if not successors:
                return 1
            return 1 + max(depth(s, visited.copy()) for s in successors)
        return depth(file_path, set())
    
    def get_transitive_dependencies(self, file_path: str):
        trans_deps = set()
        def dfs(node):
            for succ in self.graph.successors(node):
                if succ not in trans_deps:
                    trans_deps.add(succ)
                    dfs(succ)
        dfs(file_path)
        return trans_deps
    
    def get_unused_dependencies(self, package_json_path: str) -> Set[str]:
        if package_json_path not in self.package_json_cache:
            return set()
        
        package_data = self.package_json_cache[package_json_path]
        declared_deps = set()
        
        for dep_type in ['dependencies', 'devDependencies']:
            if dep_type in package_data:
                declared_deps.update(package_data[dep_type].keys())
        
        used_deps = set()
        for node in self.graph.nodes:
            if node.startswith('node_modules/'):
                package_name = node.split('/')[1]
                used_deps.add(package_name)
        
        return declared_deps - used_deps
    
    def get_missing_dependencies(self, package_json_path: str) -> Set[str]:
        if package_json_path not in self.package_json_cache:
            return set()
        
        package_data = self.package_json_cache[package_json_path]
        declared_deps = set()
        
        for dep_type in ['dependencies', 'devDependencies']:
            if dep_type in package_data:
                declared_deps.update(package_data[dep_type].keys())
        
        used_deps = set()
        for node in self.graph.nodes:
            if node.startswith('node_modules/'):
                package_name = node.split('/')[1]
                used_deps.add(package_name)
        
        return used_deps - declared_deps
    
    def analyze_bundle_impact(self, file_path: str):
        dependencies = self.get_transitive_dependencies(file_path)
        
        impact = {
            'total_dependencies': len(dependencies),
            'npm_packages': len([d for d in dependencies if d.startswith('node_modules/')]),
            'local_files': len([d for d in dependencies if not d.startswith('node_modules/')]),
            'css_files': len([d for d in dependencies if d.endswith(('.css', '.scss', '.sass'))]),
            'js_files': len([d for d in dependencies if d.endswith(('.js', '.jsx', '.ts', '.tsx'))])
        }
        
        return impact
    
    def visualize_graph(self):
        try:
            import matplotlib.pyplot as plt
            pos = nx.spring_layout(self.graph, k=1, iterations=50)
            
            # Color nodes by type
            node_colors = []
            for node in self.graph.nodes:
                if node.startswith('node_modules/'):
                    node_colors.append('lightcoral')
                elif node.endswith(('.js', '.jsx', '.ts', '.tsx')):
                    node_colors.append('lightblue')
                elif node.endswith(('.css', '.scss', '.sass')):
                    node_colors.append('lightgreen')
                elif node.endswith('.json'):
                    node_colors.append('lightyellow')
                else:
                    node_colors.append('lightgray')
            
            plt.figure(figsize=(12, 8))
            nx.draw(self.graph, pos, with_labels=True, arrows=True, 
                   node_size=1000, node_color=node_colors, 
                   font_size=8, font_color='black', edge_color='gray',
                   arrowsize=20, arrowstyle='->')
            plt.title("MERN Stack Dependency Graph")
            plt.tight_layout()
            plt.show()
        except ImportError:
            print("Matplotlib is not installed. Skipping graph visualization.")


def refine_prompt(prompt: string) ->  string:
    resp = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents = f"""
            You are a senior MERN stack architect. Your task is to take a high-level project idea and generate a detailed prompt that instructs a language model to output a production-ready MERN stack folder structure, including all directories and file names, but no file contents or code.

Analyse the {prompt} first—if it lacks clarity or scope, elaborate on it appropriately before proceeding. If the prompt is already detailed, return it as is.

project_name : {prompt}

Follow these rules when writing the refined prompt:
Prompt Template to Generate:
Project Name : 

Generate the folder structure only (no code or file contents) for a MERN stack project named .

This project is a , with the following key features:





Use MERN stack best practices:

Modular, reusable components with clear separation of concerns.

Strictly include package.json in both root and client directories to manage dependencies.

Follow the standard project layout for production-grade full-stack systems.

Include standard folders and files for:

Client-side (React): src/, public/, components/, pages/, hooks/, context/, utils/

Server-side (Node.js/Express): routes/, controllers/, models/, middleware/, config/

Database: MongoDB connection and schema definitions

Build and deployment: build/, dist/, .env files

The project structure should include, but is not limited to:

client/ – React frontend application with components, pages, and state management.

server/ – Node.js/Express backend with API routes, controllers, and database models.

shared/ – Common utilities, types, and constants used by both client and server.

config/ – Configuration files for different environments and database connections.

Follow MERN naming conventions and proper full-stack project structuring.

Return only the folder structure with relevant file names in a tree view format.
Do not include any code or file contents.

Additional Technical Requirements & Best Practices:
Maintain modularity and reusability across all React components and Node.js modules.

Use a standard production layout:

Root project directory with package.json and main configuration files

Client directory with React app structure (src/, public/, package.json)

Server directory with Express app structure (routes/, models/, controllers/, package.json)

Shared utilities and types in shared/ directory

Environment configurations in .env files for different stages

Include package.json, .env.example, .env, README.md, .gitignore, yarn.lock/package-lock.json

Placeholders for Docker and CI/CD: Dockerfile, docker-compose.yml, .github/workflows/, etc.

Client structure should have: components/, pages/, hooks/, context/, utils/, assets/, styles/

Server structure should have: routes/, controllers/, models/, middleware/, config/, utils/

The config/ folder must contain database.js, auth.js, and environment-specific configurations

📌 Front-End Architecture & Styling Guidelines:
Organize React components in a hierarchical structure with reusable UI components in components/common/

Implement proper state management using Context API or Redux (store/, actions/, reducers/)

Use CSS Modules, Styled Components, or Tailwind CSS for styling. Avoid inline styles.

Implement proper routing with React Router in pages/ directory

Include custom hooks in hooks/ directory for reusable logic

Ensure proper TypeScript support with .ts/.tsx files and type definitions

📌 Back-End Architecture Guidelines:
Follow RESTful API design principles with proper HTTP methods and status codes

Implement proper authentication and authorization middleware

Use MongoDB with Mongoose for data modeling and validation

Include proper error handling middleware and logging

Implement API versioning (e.g., /api/v1/)

Include proper CORS configuration and security middleware

Example Input:
Input: task management application

Expected Refined Prompt Output:
Project Name : task_management_app

Generate the folder structure only (no code or file contents) for a MERN stack project named task_management_app.

The project is a Task Management Application with the following key features:

Users can register, log in, and manage their personal tasks and projects.

Team leaders can create teams, assign tasks, and monitor progress.

Admins can manage users, teams, and oversee all projects.

Real-time collaboration with task updates and notifications.

Dashboard with analytics and progress tracking for different user roles.

User Roles and Capabilities:

Users: Create, edit, delete personal tasks, join teams, receive notifications.

Team Leaders: Manage team tasks, assign responsibilities, track team progress.

Admins: User management, system configuration, analytics overview.

Use MERN stack best practices:

Structure the project with modular React components and Express API routes.

Implement proper state management with Context API or Redux.

Use MongoDB with Mongoose for data persistence and validation.

Follow standard production layout with clear separation between client and server.

Include proper authentication with JWT tokens and protected routes.

Include folders for:

client/src/ (React app)

server/ (Express API)

shared/ (Common utilities)

config/ (Environment configurations)

Client structure to include:

components/ (UI components)

pages/ (Route components)

hooks/ (Custom React hooks)

context/ (State management)

utils/ (Helper functions)

assets/ (Images, icons)

styles/ (CSS/SCSS files)

Server structure to include:

routes/ (API endpoints)

controllers/ (Business logic)

models/ (MongoDB schemas)

middleware/ (Authentication, validation)

config/ (Database, environment)

utils/ (Helper functions)

Include standard files such as:

package.json in root, client/, and server/

.env.example, .env for environment variables

README.md, .gitignore, docker-compose.yml

tsconfig.json for TypeScript support

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

    prompt = f"""You are analyzing a file from a MERN stack project. Generate a detailed yet concise metadata description that captures its purpose, structure, and relationships.

**File Information**
- File Name: {filename}
- File Type: {file_type} (e.g., .js, .jsx, .ts, .tsx, .css, .json)
- Project Location: {context} (e.g., components, pages, routes, models, middleware)
- Project Idea: {refined_prompt}
- Project Structure:
{tree}
- File Content:
{file_content}

**What to include in your response:**
1. A concise 2–3 sentence summary of what this file does and how it fits into the MERN stack project.
2. If it's a React component (.jsx/.tsx):
- Mention key components, hooks, props, state management, and lifecycle methods used.
3. If it's a Node.js/Express file (.js/.ts):
- Describe API routes, controllers, middleware functions, database operations, or utility functions.
4. If it's a database model:
- Explain the schema structure, relationships, and validation rules.
5. If it's a styling file (CSS/SCSS):
- Explain the UI components or pages it styles and any CSS frameworks used.
6. If it's a configuration file (package.json, .env, config files):
- Describe the dependencies, environment variables, or build configurations it manages.
7. List **which other files or modules this file is directly coupled with**, either through imports, API calls, component usage, or database references.
8. Mention any external packages or libraries (e.g., `express`, `mongoose`, `react-router-dom`, `axios`) used here.

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
    
    prompt = f"""Generate the content of a MERN stack project file.

        Details:
        - File Name: {filename}
        - File Type: {file_type} (e.g., JavaScript, TypeScript, JSX, TSX, CSS, JSON)
        - Project Context: {context} (e.g., components, pages, routes, models, controllers, middleware, etc.)
        - Project Idea: {refined_prompt}
        - Full Folder Structure: {tree}

        Requirements:
        - Follow MERN stack best practices relevant to the file type
        - Include only necessary imports and dependencies
        - Use JSDoc comments and inline comments for clarity where applicable

        For React component files (.jsx/.tsx):
        - Use functional components with hooks
        - Add proper TypeScript types and interfaces
        - Implement proper prop validation
        - Follow React best practices for state management and lifecycle
        - Use proper component composition and reusability

        For Node.js/Express files (.js/.ts):
        - Add proper error handling and validation
        - Use async/await for asynchronous operations
        - Include proper middleware implementation
        - Follow RESTful API design principles
        - Add proper TypeScript types where applicable

        For MongoDB model files:
        - Use Mongoose schemas with proper validation
        - Include proper indexing and relationships
        - Add schema methods and virtuals where needed
        - Implement proper data sanitization

        For CSS/SCSS files:
        - Write modular, component-scoped styles
        - Use CSS Modules, Styled Components, or Tailwind CSS patterns
        - Follow BEM or other naming conventions if applicable
        - Ensure responsive design and accessibility

        For configuration files (package.json, .env, config files):
        - Include all necessary dependencies and scripts
        - Follow proper environment variable patterns
        - Add proper build and deployment configurations

        For utility and helper files:
        - Write pure, testable functions
        - Include proper error handling
        - Add comprehensive JSDoc documentation

        Output:
        - Return only the raw code as it would appear in the file (no markdown or extra formatting)
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
    dependency_analyzer: DepenedencyAnalyzer = None,
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
    You are an expert MERN stack code reviewer.

    You are reviewing the coupling accuracy of a MERN stack file by comparing:
    1. The actual imports and logical usage in the file.
    2. The declared `couples_with` list in the project's metadata.
    3. The dependencies extracted via static analysis.

    Your goal is to verify whether the declared couplings are complete, precise, and consistent with the file's true behavior.

    ---

    **File Path**: {file_path}

    ---

    **File Content**:
    {file_content}

    ---

    **Declared Metadata Couplings** (`couples_with`):
    {metadata_dict.get('couples_with', [])}

    ---

    **Statically Detected Dependencies (from code analysis)**:
    {actual_dependencies}

    ---

    **Instructions**:
    - Analyze the file's actual imports, require statements, component usage, API calls, and cross-module dependencies.
    - Compare that to the declared couplings in the metadata (`couples_with`).
    - Then compare both with the dependencies inferred via static analysis (`actual_dependencies`).
    - If you find discrepancies, please describe the issue and suggest corrections.
    - Determine if:
    1. All couplings in the code are properly captured in the metadata (including React component imports, Express route dependencies, MongoDB model references, utility functions, external packages).
    2. There are any incorrect, missing, or extra entries in the metadata.
    3. Any syntactical or logical errors in the file that prevent it from running correctly.
    4. For React files: Check component imports, hook usage, context providers, and prop dependencies.
    5. For Node.js files: Check module imports, middleware usage, database model references, and API endpoint calls.
    6. For configuration files: Check dependency declarations, environment variable usage, and build script references.

    ---

    **Return ONLY this exact JSON format**:
    {{
    "correctness": "correct" or "incorrect",
    "changes_needed": "clear explanation of what's missing, extra, or incorrect (empty string if everything is accurate)"
    }}

    ---

    **Examples**:

    Example 1 (Correct):
    {{
    "correctness": "correct",
    "changes_needed": ""    
    }}

    Example 2 (Incorrect - React Component):
    {{
    "correctness": "incorrect",
    "changes_needed": "The file imports `import {{ UserContext }} from '../context/UserContext'` but `../context/UserContext` is missing in the declared metadata. Also, metadata lists `../utils/api` but it is not used anywhere in the file. The component uses `useState` and `useEffect` hooks but `react` dependency is not listed."
    }}

    Example 3 (Incorrect - Express Route):
    {{
    "correctness": "incorrect",
    "changes_needed": "The file requires `const User = require('../models/User')` but `../models/User` is missing in the declared metadata. Also, the file uses `express.Router()` but `express` is not listed in the couplings. Metadata incorrectly lists `../middleware/validation` which is not imported."
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
    
    try:
        if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
            es6_imports = re.findall(r'import\s+(?:[^;]+\s+from\s+)?["\']([^"\']+)["\']', content)
            for imp in es6_imports:
                if not imp.startswith(('./', '../', '/')):
                    continue
                
                resolved_path = resolve_import_path(file_path, imp, project_files)
                if not resolved_path:
                    invalid_imports.append(f"Import '{imp}' in {file_path} does not exist in the project files.")
            
            require_imports = re.findall(r'require\(["\']([^"\']+)["\']\)', content)
            for imp in require_imports:
                if not imp.startswith(('./', '../', '/')):
                    continue
                
                resolved_path = resolve_import_path(file_path, imp, project_files)
                if not resolved_path:
                    invalid_imports.append(f"Require '{imp}' in {file_path} does not exist in the project files.")
            
            dynamic_imports = re.findall(r'import\(["\']([^"\']+)["\']\)', content)
            for imp in dynamic_imports:
                if not imp.startswith(('./', '../', '/')):
                    continue
                
                resolved_path = resolve_import_path(file_path, imp, project_files)
                if not resolved_path:
                    invalid_imports.append(f"Dynamic import '{imp}' in {file_path} does not exist in the project files.")
        
        elif file_path.endswith(('.css', '.scss', '.sass')):
            css_imports = re.findall(r'@import\s+["\']([^"\']+)["\']', content)
            for imp in css_imports:
                if imp.startswith('~'):
                    continue
                
                resolved_path = resolve_css_import_path(file_path, imp, project_files)
                if not resolved_path:
                    invalid_imports.append(f"CSS import '{imp}' in {file_path} does not exist in the project files.")
        
        elif file_path.endswith('.html'):
            script_srcs = re.findall(r'<script\s+[^>]*src=["\']([^"\']+)["\']', content)
            for src in script_srcs:
                if src.startswith(('http://', 'https://', '//')):
                    continue
                
                resolved_path = resolve_relative_path(file_path, src, project_files)
                if not resolved_path:
                    invalid_imports.append(f"Script src '{src}' in {file_path} does not exist in the project files.")
            
            link_hrefs = re.findall(r'<link\s+[^>]*href=["\']([^"\']+)["\']', content)
            for href in link_hrefs:
                if href.startswith(('http://', 'https://', '//')):
                    continue
                
                resolved_path = resolve_relative_path(file_path, href, project_files)
                if not resolved_path:
                    invalid_imports.append(f"Link href '{href}' in {file_path} does not exist in the project files.")
        
        elif file_path.endswith('.json'):
            try:
                data = json.loads(content)
                
                if 'scripts' in data:
                    for script_content in data['scripts'].values():
                        file_refs = re.findall(r'["\']([^"\']*\.[a-zA-Z]+)["\']', script_content)
                        for ref in file_refs:
                            resolved_path = resolve_relative_path(file_path, ref, project_files)
                            if resolved_path is None and os.path.exists(os.path.join(os.path.dirname(file_path), ref)):
                                invalid_imports.append(f"Script reference '{ref}' in {file_path} does not exist in the project files.")
                
            except json.JSONDecodeError:
                pass
    
    except Exception as e:
        # Handle any parsing errors gracefully
        print(e)
    
    return invalid_imports

def resolve_import_path(file_path: str, import_path: str, project_files: set):
    file_dir = os.path.dirname(file_path)
    
    if import_path.startswith('./') or import_path.startswith('../'):
        base_path = os.path.normpath(os.path.join(file_dir, import_path))
        
        extensions = ['.js', '.jsx', '.ts', '.tsx', '.json']
        
        for ext in extensions:
            potential_file = f"{base_path}{ext}"
            if potential_file in project_files:
                return potential_file
        
        if os.path.isdir(base_path):
            for ext in extensions:
                index_file = os.path.join(base_path, f"index{ext}")
                if index_file in project_files:
                    return index_file
    
    return None

def resolve_css_import_path(file_path: str, import_path: str, project_files: set):
    file_dir = os.path.dirname(file_path)
    base_path = os.path.normpath(os.path.join(file_dir, import_path))
    
    extensions = ['', '.css', '.scss', '.sass']
    
    for ext in extensions:
        potential_file = f"{base_path}{ext}"
        if potential_file in project_files:
            return potential_file
        
        if ext in ['.scss', '.sass']:
            partial_file = os.path.join(os.path.dirname(base_path), f"_{os.path.basename(base_path)}{ext}")
            if partial_file in project_files:
                return partial_file
    
    return None

def resolve_relative_path(file_path: str, relative_path: str, project_files: set) :
    file_dir = os.path.dirname(file_path)
    resolved_path = os.path.normpath(os.path.join(file_dir, relative_path))
    
    if resolved_path in project_files:
        return resolved_path
    
    return None


def get_project_files(metadata_dict, project_name) -> set:
    project_files = set()
    for entry in metadata_dict.get(project_name, []):
        if entry["path"].endswith('.py'):
            rel_path = os.path.relpath(entry["path"], project_name)
            project_files.add(rel_path)
    return project_files

def valid_django_naeming_conventions(code, file_apth):
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
        file_type = os.path.basename(file_apth)
        
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
                                               
def refine_for_the_change_in_file(file_content, changes_needed):
    prompt = f"""
    You are an expert MERN stack developer.

    Your task is to correct the following MERN stack project file so that its **imports and references** properly match the declared couplings and dependency expectations, based on feedback from a static analysis and metadata validation.

    ---

    **Original File Content**:
    {file_content}

    ---

    **Correction Feedback**:
    {changes_needed}

    ---

    **Requirements**:
    - Fix **only the issues mentioned in the Correction Feedback** — including:
        - Missing or incorrect imports/require statements.
        - Imports of non-existent files or modules — these should be removed.
        - Typographical errors in import statements or component/function names.
        - Syntactical errors in the file that prevent it from running correctly.
        - Missing React hooks, component imports, or context providers.
        - Incorrect Express middleware, route handlers, or database model references.
        - Missing or incorrect external package imports (e.g., react, express, mongoose, axios).
    - Ensure that all imports and references are logically correct and semantically aligned with the metadata.
    - If an import is missing, **add it**.
    - If an import is incorrect, **correct it**.
    - If an import is redundant or not used, **remove it**.
    - If an import references a file/module that does not exist in the project, **remove or replace it** as appropriate.
    - For React files: Ensure proper component imports, hook usage, and prop destructuring.
    - For Node.js files: Ensure proper module imports, middleware usage, and database connections.
    - Do **not**:
        - Add any new functionality unrelated to the correction.
        - Modify logic outside of the specified corrections.
        - Introduce any new features or components beyond what's mentioned.
    - Maintain original indentation, code structure, and MERN stack best practices.

    ---

    **Output Format**:
    - Return the corrected file content as raw code (JavaScript/TypeScript/JSX/TSX/CSS/JSON).
    - No markdown, no comments, no extra text.

    ---

    **Reminder**: Be conservative and minimal. Fix only what's necessary to make the file **logically correct and semantically aligned with the metadata**.
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
    dependency_analyzer: DepenedencyAnalyzer = None,
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

            # naming_issues = valid_django_naeming_conventions(code=content, file_apth=full_path)



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
                # if naming_issues:
                #     changes_needed += f"Naming issues found in {full_path}: {naming_issues}"
                #     print(f"Naming issues found in {full_path}: {naming_issues}")
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

        # Count indentations based on common formatting
        while temp_line.startswith('│   ') or temp_line.startswith('    ') or temp_line.startswith('│ ') or temp_line.startswith('    '):
            temp_line = temp_line[4:]
            indent += 1

        # Clean the line to get just the name
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

    # Mark files vs directories
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

# prompt = """
# Build a Transport Management System Web Application with the following modules and functionalities:

# 1. Master Module:
#     Create a module to maintain details of unorganized transporters.
#     When a new transporter is added:
#     Auto-generate a unique login ID and password.
#     These credentials should allow the transporter to log in to their portal.
# 2. Transporter Portal:
#     Once logged in, the transporter should be able to:
#     View all consignments assigned to them.
#     Update consignment status (e.g., In Transit, Delivered, Delayed, No Status).
#     Upload POD (Proof of Delivery) as an image.
#     Enter delivery details, including delivery date and remarks.
# 3. Dashboard & Reporting (for Admin):
#     A graphical dashboard showing:
#         Total consignments
#         Delivered
#         In Transit
#         No Status
#     A count of consignments by status.
#     For delivered consignments:
#         Count how many were:
#             Delivered on time
#             1–3 days delayed
#             4–6 days delayed
#             More than 6 days delayed
#         Count of delivered consignments with and without POD images.
#     Provide the ability to:
#         View, filter, and export detailed reports.
#         Download data in Excel/PDF format.
# """
# refined_prompt = refine_prompt(prompt)
# print(refined_prompt)
# project_name =extract_project_name(refined_prompt)
# # for line in lines:
# #     if "Project Name:" in line:
# #         project_name = line.split("Project Name:")[-1].strip()
# #         break
# #     else:
# #         project_name = prompt

# print(project_name)
# response = generate_folder_struct(refined_prompt)
# print(response)
# folder_tree = generate_tree(response, project_name)
# print(folder_tree.print_tree())
# # cont = response.strip().replace('```', '').strip()
# # lines = cont.split('\n')
# # if lines:
# #     project_name = lines[0].strip()
# #     print(f"Project Name: {project_name}")\
# dependency_analyzer = DepenedencyAnalyzer()
# json_file_name = "projects_metadata.json"
# metadata_dict = {project_name: []}

# output_dir = os.path.dirname(json_file_name)
# if output_dir:
#     os.makedirs(output_dir, exist_ok=True)

# # with open(json_file_name, 'w', encoding='utf-8') as f:
# #     json.dump(empty_data, f, indent=4)

# # # # dfs_tree_and_gen(folder_tree, refined_prompt, response, "", "", json_file_name, project_name=project_name,)
# dfs_tree_and_gen(root=folder_tree, refined_prompt=refined_prompt, tree_structure=response, project_name=project_name, current_path="", parent_context="", json_file_name=json_file_name, metadata_dict=metadata_dict, dependency_analyzer=dependency_analyzer)

# dependency_analyzer.visualize_graph()

# for entry in metadata_dict[project_name]:
#     path = entry["path"]
#     entry["couples_with"] = dependency_analyzer.get_dependencies(entry["path"])

# with open(json_file_name, 'w') as f:
#     json.dump(metadata_dict, f, indent=4)


# dfs_feedback_loop(folder_tree, response, project_name, current_path="", metadata_dict=metadata_dict, dependency_analyzer=dependency_analyzer, is_top_level=True)

# with open(json_file_name, 'w') as f:
#     json.dump(metadata_dict, f, indent=4)

# # def dummy_check_json_resp():
# #     resp = """```json
# #     {
# #     "correctness": "correct",
# #     "changes_needed": ""
# #     }
# #     ```"""

# #     cleaned_response = resp.strip('`').replace('json\n', '').strip()
# #     data = json.loads(cleaned_response)
# #     correctness = data["correctness"]
# #     changes_needed = data["changes_needed"]
# #     return correctness, changes_needed

# # correctness, changes_needed = dummy_check_json_resp()
# # print(f"Correctness: {correctness}")
# # print(f"Changes Needed: {changes_needed}")
# print("Happa... done, pothum da")

# # with open("Event/Event/core/models.py", 'r') as f:
# #     content = f.read()
# # print(content)
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

    # output_dir = f"generated_projects/{output_dir}"

    print("running mern script...")
    refined_prompt = refine_prompt(prompt)
    project_name =extract_project_name(refined_prompt)
    print(project_name)
    response = generate_folder_struct(refined_prompt)
    print(response)
    folder_tree = generate_tree(response, output_dir)
    print(folder_tree.print_tree())
    dependency_analyzer = DepenedencyAnalyzer()
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
