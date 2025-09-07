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
    '.svelte', '.js', '.ts', '.html', '.css', '.scss', '.sass', '.less', '.json', 
    '.md', '.yml', '.yaml', '.env', '.txt', '.png', '.ico', '.svg', '.jpg', 
    '.jpeg', '.webp', '.gif', '.sh', '.mjs'
}
GENERATABLE_FILENAMES = {
    'svelte.config.js', 'vite.config.js', 'package.json', 'tsconfig.json', 
    'tailwind.config.js', 'app.html', 'error.html', 'hooks.client.js', 
    'hooks.server.js', 'service-worker.js', 'Dockerfile', 'README.md', 
    '.gitignore', '.env', '.env.example', 'yarn.lock', 'pnpm-lock.yaml',
    'jsconfig.json', '.npmrc', '.prettierrc', 'eslint.config.js', 
    'playwright.config.js'
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
        
        if file_path.endswith(".svelte"):
            script_imports = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in script_imports:
                dependencies.add(imp)
            
            component_tags = re.findall(r'<([A-Z][a-zA-Z0-9]*)', content)
            for component in component_tags:
                dependencies.add(component)
            
            style_imports = re.findall(r'@import\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in style_imports:
                dependencies.add(imp)
            
            sveltekit_imports = re.findall(r'from\s+[\'"](\$app/[^\'"]+)[\'"]', content)
            for imp in sveltekit_imports:
                dependencies.add(imp)
            
            lib_imports = re.findall(r'from\s+[\'"](\$lib/[^\'"]+)[\'"]', content)
            for imp in lib_imports:
                dependencies.add(imp)
            
            env_imports = re.findall(r'from\s+[\'"](\$env/[^\'"]+)[\'"]', content)
            for imp in env_imports:
                dependencies.add(imp)

        elif file_path.endswith((".ts", ".js", ".mjs")):
            import_statements = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in import_statements:
                dependencies.add(imp)
            
            dynamic_imports = re.findall(r'import\([\'"]([^\'"]+)[\'"]\)', content)
            for imp in dynamic_imports:
                dependencies.add(imp)
            
            require_statements = re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', content)
            for req in require_statements:
                dependencies.add(req)
            
            sveltekit_functions = ['load', 'error', 'redirect', 'fail', 'json', 'text']
            for func in sveltekit_functions:
                if func in content:
                    dependencies.add(f"@sveltejs/kit:{func}")

        elif file_path.endswith(".json"):
            try:
                json_data = json.loads(content)
                
                if 'dependencies' in json_data:
                    for dep_name in json_data['dependencies'].keys():
                        dependencies.add(dep_name)
                
                if 'devDependencies' in json_data:
                    for dep_name in json_data['devDependencies'].keys():
                        dependencies.add(dep_name)
                
                if 'extends' in json_data:
                    extends = json_data['extends']
                    if isinstance(extends, list):
                        for layer in extends:
                            dependencies.add(layer)
                    else:
                        dependencies.add(extends)
                        
            except Exception as e:
                print(f"Error parsing JSON {file_path}: {e}")

        elif file_path.endswith((".css", ".scss", ".sass", ".less")):
            imports = re.findall(r'@import\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in imports:
                dependencies.add(imp)
            
            use_statements = re.findall(r'@use\s+[\'"]([^\'"]+)[\'"]', content)
            for use_stmt in use_statements:
                dependencies.add(use_stmt)
            
            css_vars = re.findall(r'var\(--([a-zA-Z0-9-]+)\)', content)
            for var in css_vars:
                dependencies.add(f"--{var}")

        elif file_path.endswith(".html"):
            scripts = re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', content)
            for script in scripts:
                dependencies.add(script)
            
            links = re.findall(r'<link[^>]+href=[\'"]([^\'"]+)[\'"]', content)
            for link in links:
                dependencies.add(link)
            
            svelte_components = re.findall(r'<([A-Z][a-zA-Z0-9]*)', content)
            for component in svelte_components:
                dependencies.add(component)

        elif file_path.endswith((".yml", ".yaml")):
            try:
                import yaml
                yaml_data = yaml.safe_load(content)
                
                if isinstance(yaml_data, dict) and 'jobs' in yaml_data:
                    for job_name, job_config in yaml_data['jobs'].items():
                        if 'uses' in job_config:
                            dependencies.add(job_config['uses'])
                        if 'steps' in job_config:
                            for step in job_config['steps']:
                                if isinstance(step, dict) and 'uses' in step:
                                    dependencies.add(step['uses'])
                                    
            except Exception as e:
                print(f"Error parsing YAML {file_path}: {e}")
        
        return dependencies
    
    def resolve_svelte_component(self, file_dir: str, component_name: str):
        component_file = os.path.join(file_dir, f"{component_name}.svelte")
        if os.path.exists(component_file):
            return component_file
        
        components_dir = os.path.join(file_dir, "components")
        component_file = os.path.join(components_dir, f"{component_name}.svelte")
        if os.path.exists(component_file):
            return component_file
        
        lib_components_dir = os.path.join(self.find_project_root(file_dir), "src", "lib", "components")
        component_file = os.path.join(lib_components_dir, f"{component_name}.svelte")
        if os.path.exists(component_file):
            return component_file
        
        return None
    
    def resolve_sveltekit_path(self, file_dir: str, import_path: str):
        if import_path.startswith('$lib'):
            project_root = self.find_project_root(file_dir)
            resolved_path = import_path.replace('$lib', os.path.join(project_root, 'src', 'lib'))
            return resolved_path
        
        if import_path.startswith('$app'):
            return import_path
        
        if import_path.startswith('$env'):
            return import_path
        
        if import_path.startswith('./') or import_path.startswith('../'):
            return os.path.join(file_dir, import_path)
        
        return import_path
    
    def find_project_root(self, current_dir: str):
        while current_dir != os.path.dirname(current_dir):
            if (os.path.exists(os.path.join(current_dir, 'package.json')) or 
                os.path.exists(os.path.join(current_dir, 'svelte.config.js')) or
                os.path.exists(os.path.join(current_dir, 'vite.config.js'))):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        return current_dir
    
    def get_dependencies(self, file_path: str) -> List[str]:
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        return list(self.graph.predecessors(file_path))
    
    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)
    
    def get_npm_packages(self):
        packages = set()
        for node in self.graph.nodes:
            if node.endswith("package.json"):
                for dep in self.get_dependencies(node):
                    if not dep.startswith('./') and not dep.endswith(('.svelte', '.js', '.ts')):
                        packages.add(dep)
        return packages
    
    def get_svelte_components(self):
        components = set()
        for node in self.graph.nodes:
            if node.endswith(".svelte"):
                for dep in self.get_dependencies(node):
                    if dep.endswith('.svelte') or dep[0].isupper():
                        components.add(dep)
        return components
    
    def get_sveltekit_imports(self):
        sveltekit_imports = set()
        sveltekit_modules = ['$app/environment', '$app/forms', '$app/navigation', 
                           '$app/paths', '$app/state', '$app/stores', '$env/dynamic/private',
                           '$env/dynamic/public', '$env/static/private', '$env/static/public',
                           '$lib', '$lib/server', '@sveltejs/kit']
        
        for node in self.graph.nodes:
            for dep in self.get_dependencies(node):
                for module in sveltekit_modules:
                    if dep.startswith(module):
                        sveltekit_imports.add(dep)
        return sveltekit_imports
    
    def visualize_graph(self):
        try:
            import matplotlib.pyplot as plt
            pos = nx.spring_layout(self.graph)
            
            node_colors = []
            for node in self.graph.nodes:
                if node.endswith('.svelte'):
                    node_colors.append('lightgreen')
                elif node.endswith(('.ts', '.js')):
                    node_colors.append('lightblue')
                elif node.endswith(('.css', '.scss')):
                    node_colors.append('lightcoral')
                else:
                    node_colors.append('lightgray')
            
            nx.draw(self.graph, pos, with_labels=True, arrows=True, 
                   node_size=2000, node_color=node_colors, 
                   font_size=8, font_color='black', edge_color='gray')
            plt.title("SvelteKit Dependency Graph")
            plt.show()
        except ImportError:
            print("Matplotlib is not installed. Skipping graph visualization.")


def refine_prompt(prompt: string) ->  string:
    resp = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents = f"""
            You are a senior Svelte + SvelteKit architect. Your task is to take a high-level project idea and generate a detailed prompt that instructs a language model to output a production-ready Svelte + SvelteKit application folder structure, including all directories and file names, but no file contents or code.

Analyse the {prompt} first—if it lacks clarity or scope, elaborate on it appropriately before proceeding. If the prompt is already detailed, return it as is.

project_name : {prompt}

Follow these rules when writing the refined prompt:
Prompt Template to Generate:
Project Name : 

Generate the folder structure only (no code or file contents) for a Svelte + SvelteKit project named .

This project is a , with the following key features:





Use Svelte + SvelteKit best practices:

Modular, reusable component structure with clear separation of concerns.

Strictly include package.json in the root directory to manage dependencies.

Follow the standard SvelteKit framework layout for production-grade applications.

Include standard folders and files for:

Routes: src/routes/

Components: src/lib/components/

Utilities: src/lib/utils/

Stores: src/lib/stores/

Server API: src/routes/api/

Static assets: static/

Styling: src/lib/styles/

Configuration: svelte.config.js, vite.config.js

The application modules should include, but are not limited to:

components – reusable Svelte components with proper organization.

routes – file-based routing following SvelteKit conventions.

lib – shared utilities, stores, and business logic.

stores – Svelte stores for state management.

hooks – client and server hooks for request handling.

Follow Svelte and SvelteKit naming conventions and proper project structuring.

Return only the folder structure with relevant file names in a tree view format.
Do not include any code or file contents.

Additional Technical Requirements & Best Practices:
Maintain modularity and reusability across all Svelte components.

Use a standard SvelteKit production layout:

Root project directory with package.json and svelte.config.js

src/routes directory for file-based routing

src/lib directory for shared components and utilities

src/app.html for the main HTML template

static directory for static assets

Include package.json, .env.example, .env, README.md, .gitignore

Placeholders for deployment: Dockerfile, docker-compose.yml, .github/workflows/, etc.

Each component should follow Svelte SFC structure with proper organization

The styling should support CSS preprocessors and modern CSS features

📌 Front-End Development Guidelines:
Use TypeScript for all development. All logic must reside in properly typed .svelte, .ts files organized under appropriate directories.

Leverage Svelte's reactive system with proper component architecture. Include Svelte components with clear separation of concerns and proper props/events definitions.

Use SvelteKit's built-in features for routing, loading data, and form actions. Organize custom utilities and stores in dedicated directories.

Ensure proper SEO optimization, server-side rendering, and performance optimization through SvelteKit's built-in features.

Example Input:
Input: e-commerce marketplace

Expected Refined Prompt Output:
Project Name : ecommerce_marketplace

Generate the folder structure only (no code or file contents) for a Svelte + SvelteKit project named ecommerce_marketplace.

The project is an E-commerce Marketplace with the following key features:

Users can browse products, add items to cart, and complete purchases.

Vendors can register, manage product listings, and track sales.

Administrators can manage users, moderate listings, and oversee platform operations.

Real-time inventory tracking and order management.

User Roles and Capabilities:

Customers: Browse products, manage cart, place orders, and track shipments.

Vendors: Manage product catalog, process orders, and view analytics.

Admins: Platform management, user moderation, and system configuration.

Use Svelte + SvelteKit best practices:

Structure the project with modular Svelte component architecture.

Implement file-based routing with SvelteKit routes.

Use TypeScript for all development with proper typing.

Implement proper state management using Svelte stores and API integration.

Follow standard SvelteKit production layout with clear component boundaries.

Include folders for:

src/routes/

src/lib/components/

src/lib/stores/

src/routes/api/

Application modules to include:

components

routes

lib

stores

hooks

static

Include standard Svelte/SvelteKit files such as:

package.json and svelte.config.js in the root

Svelte components in src/lib/components/

Route pages in src/routes/

API routes in src/routes/api/

Stores in src/lib/stores/ directory

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

    prompt = f"""You are analyzing a file from a Svelte + SvelteKit project. Generate a detailed yet concise metadata description that captures its purpose, structure, and relationships.

File Information

File Name: {filename}

File Type: {file_type} (e.g., .svelte, .ts, .js, .css, .scss, .json)

Project Location: {context} (e.g., src/routes/, src/lib/components/, src/lib/stores/, src/routes/api/, src/lib/)

Project Idea: {refined_prompt}

Project Structure:
{tree}

File Content:
{file_content}

What to include in your response:

A concise 2–3 sentence summary of what this file does and how it fits into the Svelte + SvelteKit project.

If it's a Svelte file (.svelte):

Mention key components, props, events, stores used, and template structure.

If it's a TypeScript/JavaScript file (.ts/.js):

Describe the utility, store, hook, or API route it provides and any Svelte/SvelteKit APIs used.

If it's a configuration file (.json/.js/.ts):

Explain the dependencies, build settings, or project configuration it manages.

If it's a styling file (.css/.scss/.sass):

Describe the styling approach, component styles, or global styles it provides.

List which other files or modules this file is directly coupled with, either through imports, component usage, or store dependencies.

Mention any external packages, Svelte/SvelteKit frameworks, or libraries (e.g., svelte, @sveltejs/kit, @sveltejs/adapter-auto, tailwindcss) used here.

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
    
    prompt = f"""Generate the content of a Vue + Nuxt project file.

Details:

File Name: {filename}

File Type: {file_type} (e.g., Vue, TypeScript, JavaScript, JSON, CSS, SCSS, HTML)

Project Context: {context} (e.g., pages/, components/, composables/, server/api/, layouts/, middleware/, etc.)

Project Idea: {refined_prompt}

Full Folder Structure: {tree}

Requirements:

Follow Vue + Nuxt best practices relevant to the file type

Include only necessary imports or dependencies

Use documentation comments and inline comments for clarity where applicable

For Vue files (.vue):
Use Vue 3 Composition API with proper TypeScript typing

Include comprehensive prop definitions and emits

Add JSDoc comments for components and complex logic

Follow Vue naming conventions and component structure

Implement proper reactivity and lifecycle management

Use Nuxt auto-imports and composables appropriately

For TypeScript/JavaScript files (.ts/.js):
Use proper TypeScript typing throughout

Implement Vue/Nuxt best practices with composables and utilities

Include proper error handling and validation

Use Nuxt auto-imports and built-in composables

Add comprehensive JSDoc comments for functions

Follow modern ES6+ patterns and async/await

For Configuration files (.json/.js/.ts):
Include all necessary dependencies and their appropriate versions

Configure proper build settings and development parameters

Set up Nuxt modules and plugins correctly

Configure TypeScript, ESLint, and other tooling

Set up development and production environment variables

For Styling files (.css/.scss/.sass):
Write modular, reusable styles with proper organization

Follow modern CSS practices and naming conventions (BEM, utility-first, etc.)

Ensure responsive design and cross-browser compatibility

Use CSS custom properties and modern features

Implement proper component scoping and global styles

For HTML template files:
Write clean, semantic HTML with proper accessibility

Avoid inline JavaScript and styles

Include proper meta tags and SEO optimization

Use responsive design principles and modern HTML5 features

Implement proper form validation and user experience patterns

For Server API files:
Write clean, RESTful API endpoints with proper validation

Use Nuxt server utilities and middleware appropriately

Include comprehensive error handling and status codes

Add proper authentication and authorization checks

Follow Node.js and Nitro best practices

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
    You are an expert Svelte + SvelteKit code reviewer.

You are reviewing the coupling accuracy of a Svelte + SvelteKit file by comparing:

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

Analyze the file's actual import statements, component usage, store references, and cross-module dependencies.

For Svelte files: Check import statements, component references, store usage, and template dependencies.

For TypeScript/JavaScript files: Check import statements, function exports, store definitions, and utility usage.

For Configuration files: Check dependency declarations, module configurations, and build settings.

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
"changes_needed": "The file imports import {"userStore"} from '$lib/stores/user' but lib/stores/user is missing in the declared metadata. Also, metadata lists @sveltejs/kit but it should be @sveltejs/kit/navigation as the actual import. The file also uses $page store but this SvelteKit built-in is not captured in the metadata."
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
    
    if file_ext == '.svelte':
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
        component_pattern = r'<([A-Z][a-zA-Z0-9]*)'
        store_pattern = r'\$([a-zA-Z][a-zA-Z0-9]*)'
        
        import_matches = re.findall(import_pattern, content)
        component_matches = re.findall(component_pattern, content)
        store_matches = re.findall(store_pattern, content)
        
        for imp in import_matches:
            if imp.startswith('./') or imp.startswith('../'):
                file_dir = os.path.dirname(file_path)
                resolved_path = os.path.normpath(os.path.join(file_dir, imp))
                
                potential_files = [
                    resolved_path,
                    resolved_path + '.svelte',
                    resolved_path + '.ts',
                    resolved_path + '.js',
                    os.path.join(resolved_path, 'index.svelte'),
                    os.path.join(resolved_path, 'index.ts'),
                    os.path.join(resolved_path, 'index.js')
                ]
                
                if not any(pf in project_files for pf in potential_files):
                    invalid_imports.append(f"Local import '{imp}' in {file_path} does not exist")
            
            elif imp.startswith('$lib/') or imp.startswith('$app/') or imp.startswith('$env/'):
                if imp.startswith('$lib/'):
                    project_root = imp.replace('$lib/', 'src/lib/')
                elif imp.startswith('$app/'):
                    project_root = imp  # $app is built-in SvelteKit module
                elif imp.startswith('$env/'):
                    project_root = imp  # $env is built-in SvelteKit module
                
                if not imp.startswith('$app/') and not imp.startswith('$env/'):
                    potential_files = [
                        project_root,
                        project_root + '.svelte',
                        project_root + '.ts',
                        project_root + '.js',
                        os.path.join(project_root, 'index.svelte'),
                        os.path.join(project_root, 'index.ts'),
                        os.path.join(project_root, 'index.js')
                    ]
                    
                    if not any(pf in project_files for pf in potential_files):
                        invalid_imports.append(f"Alias import '{imp}' in {file_path} does not exist")
            
            elif not any(imp.startswith(external) for external in [
                'svelte', '@sveltejs/kit', '@sveltejs/', 'node:'
            ]):
                package_json_path = 'package.json'
                if package_json_path in project_files:
                    try:
                        with open(package_json_path, 'r') as f:
                            package_content = f.read()
                        if f'"{imp}"' not in package_content and f"'{imp}'" not in package_content:
                            invalid_imports.append(f"NPM package '{imp}' not found in package.json dependencies")
                    except:
                        pass
        
        for component in component_matches:
            component_paths = [
                f"src/lib/components/{component}.svelte",
                f"src/lib/components/{component}/index.svelte",
                f"src/lib/components/{component.lower()}.svelte"
            ]
            if not any(cp in project_files for cp in component_paths):
                invalid_imports.append(f"Component '{component}' in {file_path} does not exist in src/lib/components directory")
        
        for store in store_matches:
            if store not in ['page', 'updated', 'navigating']:  # Built-in SvelteKit stores
                store_paths = [
                    f"src/lib/stores/{store}.ts",
                    f"src/lib/stores/{store}.js",
                    f"src/lib/stores/index.ts",
                    f"src/lib/stores/index.js"
                ]
                if not any(sp in project_files for sp in store_paths):
                    invalid_imports.append(f"Store '{store}' in {file_path} does not exist")
    
    elif file_ext in ['.ts', '.js', '.mjs']:
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
        dynamic_import_pattern = r'import\([\'"]([^\'"]+)[\'"]\)'
        require_pattern = r'require\([\'"]([^\'"]+)[\'"]\)'
        
        import_matches = re.findall(import_pattern, content)
        dynamic_matches = re.findall(dynamic_import_pattern, content)
        require_matches = re.findall(require_pattern, content)
        
        all_imports = import_matches + dynamic_matches + require_matches
        
        for imp in all_imports:
            if imp.startswith('./') or imp.startswith('../'):
                file_dir = os.path.dirname(file_path)
                resolved_path = os.path.normpath(os.path.join(file_dir, imp))
                
                potential_files = [
                    resolved_path,
                    resolved_path + '.ts',
                    resolved_path + '.js',
                    resolved_path + '.mjs',
                    resolved_path + '.svelte',
                    os.path.join(resolved_path, 'index.ts'),
                    os.path.join(resolved_path, 'index.js'),
                    os.path.join(resolved_path, 'index.mjs'),
                    os.path.join(resolved_path, 'index.svelte')
                ]
                
                if not any(pf in project_files for pf in potential_files):
                    invalid_imports.append(f"Local import '{imp}' in {file_path} does not exist")
            
            elif imp.startswith('$lib/') or imp.startswith('$app/') or imp.startswith('$env/'):
                if imp.startswith('$lib/'):
                    project_root = imp.replace('$lib/', 'src/lib/')
                    potential_files = [
                        project_root,
                        project_root + '.ts',
                        project_root + '.js',
                        project_root + '.svelte',
                        os.path.join(project_root, 'index.ts'),
                        os.path.join(project_root, 'index.js'),
                        os.path.join(project_root, 'index.svelte')
                    ]
                    
                    if not any(pf in project_files for pf in potential_files):
                        invalid_imports.append(f"Alias import '{imp}' in {file_path} does not exist")
            
            elif not any(imp.startswith(external) for external in [
                'svelte', '@sveltejs/kit', '@sveltejs/', 'node:', 'vite'
            ]):
                package_json_path = 'package.json'
                if package_json_path in project_files:
                    try:
                        with open(package_json_path, 'r') as f:
                            package_content = f.read()
                        if f'"{imp}"' not in package_content and f"'{imp}'" not in package_content:
                            invalid_imports.append(f"NPM package '{imp}' not found in package.json dependencies")
                    except:
                        pass
    
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
                
                if 'workspaces' in json_data:
                    for workspace in json_data['workspaces']:
                        workspace_package = os.path.join(workspace, 'package.json')
                        if workspace_package not in project_files:
                            invalid_imports.append(f"Workspace '{workspace}' does not contain package.json")
                            
            except Exception:
                pass
        
        elif 'tsconfig.json' in file_path or 'jsconfig.json' in file_path:
            try:
                json_data = json.loads(content)
                
                if 'extends' in json_data:
                    extends_path = json_data['extends']
                    if not extends_path.startswith('@') and extends_path not in project_files:
                        invalid_imports.append(f"Extended TypeScript config '{extends_path}' does not exist")
                
                if 'compilerOptions' in json_data and 'paths' in json_data['compilerOptions']:
                    for alias, paths in json_data['compilerOptions']['paths'].items():
                        for path in paths:
                            resolved_path = path.replace('/*', '')
                            if not any(f.startswith(resolved_path) for f in project_files):
                                invalid_imports.append(f"TypeScript path mapping '{resolved_path}' does not exist")
                                
            except Exception:
                pass
    
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
            
            elif style_import.startswith('$lib/'):
                project_root = style_import.replace('$lib/', 'src/lib/')
                potential_files = [
                    project_root,
                    project_root + '.css',
                    project_root + '.scss',
                    project_root + '.sass',
                    project_root + '.less'
                ]
                
                if not any(pf in project_files for pf in potential_files):
                    invalid_imports.append(f"Style alias import '{style_import}' in {file_path} does not exist")
        
        for url_ref in url_matches:
            if not url_ref.startswith('http') and not url_ref.startswith('data:') and not url_ref.startswith('//'):
                if url_ref.startswith('/'):
                    static_path = 'static' + url_ref
                    if static_path not in project_files:
                        invalid_imports.append(f"CSS URL reference '{url_ref}' in {file_path} does not exist in static folder")
                elif url_ref not in project_files:
                    invalid_imports.append(f"CSS URL reference '{url_ref}' in {file_path} does not exist")
    
    elif file_ext == '.html':
        script_pattern = r'<script[^>]+src=[\'"]([^\'"]+)[\'"]'
        link_pattern = r'<link[^>]+href=[\'"]([^\'"]+)[\'"]'
        
        script_matches = re.findall(script_pattern, content)
        link_matches = re.findall(link_pattern, content)
        
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
    
    elif file_ext in ['.yml', '.yaml']:
        try:
            import yaml
            yaml_data = yaml.safe_load(content)
            
            if isinstance(yaml_data, dict) and 'jobs' in yaml_data:
                for job_name, job_config in yaml_data['jobs'].items():
                    if 'uses' in job_config:
                        action_ref = job_config['uses']
                        if not action_ref.startswith('actions/') and not action_ref.startswith('.'):
                            invalid_imports.append(f"GitHub Action '{action_ref}' reference may be invalid")
                    
                    if 'steps' in job_config:
                        for step in job_config['steps']:
                            if isinstance(step, dict) and 'uses' in step:
                                action_ref = step['uses']
                                if not action_ref.startswith('actions/') and not action_ref.startswith('.'):
                                    invalid_imports.append(f"GitHub Action step '{action_ref}' reference may be invalid")
                                    
        except Exception:
            pass
    
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
    You are an expert Vue + Nuxt developer.

Your task is to correct the following Vue + Nuxt project file so that its imports, dependencies, and references properly match the declared couplings and dependency expectations, based on feedback from a static analysis and metadata validation.

Original File Content:
{file_content}

Correction Feedback:
{changes_needed}

Requirements:

Fix only the issues mentioned in the Correction Feedback — including:

Missing or incorrect import statements and module references.

Imports of non-existent components, composables, or utilities — these should be removed.

Typographical errors in import statements, component names, or function names.

Syntactical errors in the file that prevent it from compiling correctly.

Missing package dependencies in package.json files.

Incorrect component references or composable usage.

Missing or incorrect Vue/Nuxt auto-imports.

Ensure that all imports and references are logically correct and semantically aligned with the metadata.

If an import statement is missing, add it.

If an import statement is incorrect, correct it.

If an import statement is redundant or not used, remove it.

If an import references a component/module that does not exist in the project, remove or replace it as appropriate.

For Vue files, ensure proper component imports and composable usage.

For TypeScript files, ensure proper typing and module references.

For configuration files, ensure proper dependency declarations and versions.

For styling files, ensure proper import paths and asset references.

Do not:

Add any new functionality unrelated to the correction.

Modify logic outside of the specified corrections.

Introduce any new components or composables beyond what's mentioned.

Maintain original indentation, code structure, and Vue/Nuxt best practices.

Output Format:

Return the corrected file content as raw code (Vue, TypeScript, CSS, JSON, etc.).

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
