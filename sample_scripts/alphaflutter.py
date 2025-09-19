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
    '.dart', '.html', '.css', '.scss', '.sass', '.less', '.json', '.js', '.ts',
    '.md', '.yml', '.yaml', '.env', '.txt', '.png', '.ico', '.svg', '.jpg', 
    '.jpeg', '.webp', '.gif', '.sh', '.gradle', '.kt', '.swift', '.xml',
    '.plist', '.properties', '.lock', '.g.dart', '.freezed.dart'
}

GENERATABLE_FILENAMES = {
    'main.dart', 'pubspec.yaml', 'pubspec.lock', 'analysis_options.yaml',
    'Dockerfile', 'docker-compose.yml', 'README.md', '.gitignore', 
    '.env', '.env.example', 'Makefile', 'android_app_build.gradle',
    'build.gradle', 'gradle.properties', 'settings.gradle',
    'Info.plist', 'Runner.xcodeproj', 'AppDelegate.swift',
    'MainActivity.kt', 'AndroidManifest.xml', 'flutter_launcher_icons.yaml',
    'firebase_options.dart', 'google-services.json', 'GoogleService-Info.plist'
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
        
        if file_path.endswith(".dart"):
            import_statements = re.findall(r'import\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in import_statements:
                dependencies.add(imp)
            
            export_statements = re.findall(r'export\s+[\'"]([^\'"]+)[\'"]', content)
            for exp in export_statements:
                dependencies.add(exp)
            
            part_statements = re.findall(r'part\s+[\'"]([^\'"]+)[\'"]', content)
            for part in part_statements:
                dependencies.add(part)
            
            part_of_statements = re.findall(r'part\s+of\s+[\'"]([^\'"]+)[\'"]', content)
            for part_of in part_of_statements:
                dependencies.add(part_of)
            
            asset_references = re.findall(r'[\'"]assets/([^\'"]+)[\'"]', content)
            for asset in asset_references:
                dependencies.add(f"assets/{asset}")
            
            route_definitions = re.findall(r'[\'"](/[^\'"]*)[\'"]', content)
            for route in route_definitions:
                if route.startswith('/') and len(route) > 1:
                    dependencies.add(f"route:{route}")
            
            class_usage = re.findall(r'class\s+([A-Z][a-zA-Z0-9]*)', content)
            for class_name in class_usage:
                dependencies.add(f"class:{class_name}")

        elif file_path.endswith("pubspec.yaml"):
            try:
                import yaml
                yaml_data = yaml.safe_load(content)
                
                if isinstance(yaml_data, dict):
                    if 'dependencies' in yaml_data:
                        for dep_name in yaml_data['dependencies'].keys():
                            if dep_name != 'flutter':
                                dependencies.add(dep_name)
                    
                    if 'dev_dependencies' in yaml_data:
                        for dep_name in yaml_data['dev_dependencies'].keys():
                            dependencies.add(dep_name)
                    
                    if 'flutter' in yaml_data and 'assets' in yaml_data['flutter']:
                        for asset in yaml_data['flutter']['assets']:
                            dependencies.add(asset)
                    
                    if 'flutter' in yaml_data and 'fonts' in yaml_data['flutter']:
                        for font_family in yaml_data['flutter']['fonts']:
                            if 'fonts' in font_family:
                                for font in font_family['fonts']:
                                    if 'asset' in font:
                                        dependencies.add(font['asset'])
                        
            except Exception as e:
                print(f"Error parsing pubspec.yaml {file_path}: {e}")

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

        elif file_path.endswith(".html"):
            scripts = re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', content)
            for script in scripts:
                dependencies.add(script)
            
            links = re.findall(r'<link[^>]+href=[\'"]([^\'"]+)[\'"]', content)
            for link in links:
                dependencies.add(link)
            
            img_tags = re.findall(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', content)
            for img in img_tags:
                dependencies.add(img)

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

        elif file_path.endswith(".ts"):
            import_statements = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in import_statements:
                dependencies.add(imp)
            
            require_statements = re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', content)
            for req in require_statements:
                dependencies.add(req)

        elif file_path.endswith(".gradle"):
            implementation_deps = re.findall(r'implementation\s+[\'"]([^\'"]+)[\'"]', content)
            for dep in implementation_deps:
                dependencies.add(dep)
            
            api_deps = re.findall(r'api\s+[\'"]([^\'"]+)[\'"]', content)
            for dep in api_deps:
                dependencies.add(dep)
            
            test_deps = re.findall(r'testImplementation\s+[\'"]([^\'"]+)[\'"]', content)
            for dep in test_deps:
                dependencies.add(dep)

        elif file_path.endswith(".kt"):
            import_statements = re.findall(r'import\s+([^\s]+)', content)
            for imp in import_statements:
                dependencies.add(imp)
            
            class_usage = re.findall(r'class\s+([A-Z][a-zA-Z0-9]*)', content)
            for class_name in class_usage:
                dependencies.add(f"class:{class_name}")

        elif file_path.endswith(".swift"):
            import_statements = re.findall(r'import\s+([^\s]+)', content)
            for imp in import_statements:
                dependencies.add(imp)
            
            class_usage = re.findall(r'class\s+([A-Z][a-zA-Z0-9]*)', content)
            for class_name in class_usage:
                dependencies.add(f"class:{class_name}")

        elif file_path.endswith(".xml"):
            if "AndroidManifest.xml" in file_path:
                permissions = re.findall(r'<uses-permission[^>]+android:name=[\'"]([^\'"]+)[\'"]', content)
                for perm in permissions:
                    dependencies.add(f"permission:{perm}")
                
                activities = re.findall(r'<activity[^>]+android:name=[\'"]([^\'"]+)[\'"]', content)
                for activity in activities:
                    dependencies.add(f"activity:{activity}")
            
            drawable_refs = re.findall(r'@drawable/([a-zA-Z0-9_]+)', content)
            for drawable in drawable_refs:
                dependencies.add(f"drawable:{drawable}")
            
            string_refs = re.findall(r'@string/([a-zA-Z0-9_]+)', content)
            for string in string_refs:
                dependencies.add(f"string:{string}")

        elif file_path.endswith("Makefile"):
            target_deps = re.findall(r'^([a-zA-Z0-9_-]+):\s*([a-zA-Z0-9_\s-]*)', content, re.MULTILINE)
            for target, deps in target_deps:
                if deps.strip():
                    for dep in deps.split():
                        dependencies.add(f"make:{dep}")
        
        return dependencies
    
    def resolve_dart_import(self, file_dir: str, import_path: str):
        if import_path.startswith('./') or import_path.startswith('../'):
            return os.path.join(file_dir, import_path)
        
        if import_path.startswith('package:'):
            return import_path
        
        project_root = self.find_project_root(file_dir)
        if project_root:
            lib_path = os.path.join(project_root, 'lib', import_path)
            if os.path.exists(lib_path):
                return lib_path
        
        return import_path
    
    def find_project_root(self, current_dir: str):
        while current_dir != os.path.dirname(current_dir):
            if (os.path.exists(os.path.join(current_dir, 'pubspec.yaml')) or 
                os.path.exists(os.path.join(current_dir, 'lib'))):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        return current_dir
    
    def get_dependencies(self, file_path: str) -> List[str]:
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        return list(self.graph.predecessors(file_path))
    
    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)
    
    def get_dart_packages(self):
        packages = set()
        for node in self.graph.nodes:
            if node.endswith("pubspec.yaml"):
                for dep in self.get_dependencies(node):
                    if not dep.startswith('./') and not dep.endswith('.dart'):
                        packages.add(dep)
        return packages
    
    def get_flutter_routes(self):
        routes = set()
        for node in self.graph.nodes:
            if node.endswith(".dart"):
                for dep in self.get_dependencies(node):
                    if dep.startswith('route:'):
                        routes.add(dep.replace('route:', ''))
        return routes
    
    def get_assets(self):
        assets = set()
        for node in self.graph.nodes:
            for dep in self.get_dependencies(node):
                if dep.startswith('assets/'):
                    assets.add(dep)
        return assets
    
    def get_classes(self):
        classes = set()
        for node in self.graph.nodes:
            if node.endswith((".dart", ".kt", ".swift")):
                for dep in self.get_dependencies(node):
                    if dep.startswith('class:'):
                        classes.add(dep.replace('class:', ''))
        return classes
    
    def get_permissions(self):
        permissions = set()
        for node in self.graph.nodes:
            if node.endswith(".xml"):
                for dep in self.get_dependencies(node):
                    if dep.startswith('permission:'):
                        permissions.add(dep.replace('permission:', ''))
        return permissions
    
    def visualize_graph(self):
        try:
            import matplotlib.pyplot as plt
            pos = nx.spring_layout(self.graph)
            
            node_colors = []
            for node in self.graph.nodes:
                if node.endswith('.dart'):
                    node_colors.append('lightblue')
                elif node.endswith(('.html', '.xml')):
                    node_colors.append('lightgreen')
                elif node.endswith(('.css', '.scss')):
                    node_colors.append('lightcoral')
                elif node.endswith(('pubspec.yaml', 'pubspec.lock')):
                    node_colors.append('lightyellow')
                elif node.endswith(('.kt', '.swift')):
                    node_colors.append('lightpink')
                elif node.endswith('.gradle'):
                    node_colors.append('lightcyan')
                else:
                    node_colors.append('lightgray')
            
            nx.draw(self.graph, pos, with_labels=True, arrows=True, 
                   node_size=2000, node_color=node_colors, 
                   font_size=8, font_color='black', edge_color='gray')
            plt.title("Flutter Dependency Graph")
            plt.show()
        except ImportError:
            print("Matplotlib is not installed. Skipping graph visualization.")

def refine_prompt(prompt: string) ->  string:
    resp = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents = f"""
            You are a senior Flutter architect. Your task is to take a high-level project idea and generate a detailed prompt that instructs a language model to output a production-ready Flutter application folder structure, including all directories and file names, but no file contents or code.

Analyse the {prompt} first—if it lacks clarity or scope, elaborate on it appropriately before proceeding. If the prompt is already detailed, return it as is.

project_name : {prompt}

Follow these rules when writing the refined prompt:

Prompt Template to Generate:

Project Name :

Generate the folder structure only (no code or file contents) for a Flutter project named .

This project is a , with the following key features:

Use Flutter best practices:

Modular, reusable widget structure with clear separation of concerns.

Strictly include pubspec.yaml in the root directory to manage dependencies.

Follow the standard Flutter project layout for production-grade applications.

Include standard folders and files for:

Screens: lib/screens/

Widgets: lib/widgets/

Models: lib/models/

Services: lib/services/

Providers/State Management: lib/providers/ or lib/bloc/

Utils: lib/utils/

Constants: lib/constants/

Assets: assets/

Configuration: lib/config/

Main entry point: lib/main.dart

The application modules should include, but are not limited to:

screens – UI screens and page components with proper organization

widgets – reusable custom widgets and components

models – data structures and entity models

services – API calls, database operations, and external service integrations

providers/bloc – state management and business logic

utils – helper functions and utilities

constants – app constants, themes, and configuration values

Follow Flutter and Dart naming conventions and proper project structuring.

Return only the folder structure with relevant file names in a tree view format.
Do not include any code or file contents.

Additional Technical Requirements & Best Practices
Maintain modularity and reusability across all Flutter packages.

Use a standard Flutter project layout:

Root project directory with pubspec.yaml and lib/main.dart

Screens directory for UI pages and navigation

Widgets directory for reusable components

Models directory for data structures

Services directory for business logic and API integration

State management directory (providers/, bloc/, or riverpod/)

Utils directory for helper functions

Constants directory for app-wide constants

Assets directory for images, fonts, and other resources

Platform-specific directories: android/, ios/, web/, windows/, macos/, linux/

Include pubspec.yaml, pubspec.lock, analysis_options.yaml, README.md, .gitignore

Placeholders for deployment: Dockerfile, .github/workflows/, firebase.json, etc.

Each package should follow Dart conventions with proper organization

The application should support multiple platforms (iOS, Android, Web, Desktop)

📱 Flutter Development Guidelines
Use Flutter packages for dependency management. All logic must reside in properly structured .dart files organized under appropriate directories.

Leverage Flutter's widget architecture with proper state management. Include screens with clear separation of concerns and proper widget composition.

Use structured error handling and logging throughout the application. Organize custom widgets and utilities in dedicated packages.

Ensure proper responsive design, platform integration, and performance optimization through Flutter's built-in features and community packages.

Example Input
Input: social media app

Expected Refined Prompt Output
Project Name : social_media_app

Generate the folder structure only (no code or file contents) for a Flutter project named social_media_app.

The project is a Social Media App with the following key features:

Users can create profiles, post content, and interact with other users

Real-time messaging and notifications

Photo and video sharing capabilities

Social features like likes, comments, and follows

Content discovery and personalized feeds

User Roles and Capabilities:

Users: Create posts, interact with content, manage profile, and connect with others

Moderators: Content moderation and user management

Admins: Platform management and analytics

Use Flutter best practices:

Structure the project with modular Flutter architecture.

Implement responsive UI with proper state management.

Use Flutter packages for dependency management with proper versioning.

Implement proper API integration and local data persistence.

Follow standard Flutter project layout with clear package boundaries.

Include folders for:

lib/screens/

lib/widgets/

lib/models/

lib/services/

lib/providers/

lib/utils/

lib/constants/

assets/

Application modules to include:

screens

widgets

models

services

providers

utils

constants

config

Include standard Flutter files such as:

pubspec.yaml and lib/main.dart in the root

Screen files in lib/screens/ directory

Widget definitions in lib/widgets/ directory

Model classes in lib/models/ directory

Service logic in lib/services/ directory

State management in lib/providers/ directory

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

    prompt = f"""You are analyzing a file from a Flutter project. Generate a detailed yet concise metadata description that captures its purpose, structure, and relationships.

File Information

File Name: {filename}

File Type: {file_type} (e.g., .dart, .yaml, .json, .xml, .gradle, .swift, .kt, .html, .css)

Project Location: {context} (e.g., lib/screens/, lib/widgets/, lib/models/, lib/services/, lib/providers/, lib/utils/, assets/, android/, ios/)

Project Idea: {refined_prompt}

Project Structure:
{tree}

File Content:
{file_content}

What to include in your response:

A concise 2–3 sentence summary of what this file does and how it fits into the Flutter project.

If it's a Dart file (.dart):

Mention key classes, widgets, functions, mixins, packages imported, and UI components or business logic implemented.

If it's a configuration file (pubspec.yaml):

Describe the dependencies, Flutter SDK version, assets, and package configuration it manages.

If it's a platform-specific file (.gradle/.kt/.swift/.xml):

Explain the platform configuration, native integrations, or build settings it manages.

If it's an asset configuration file (.json):

Explain the app settings, localization data, or configuration parameters it manages.

If it's a template file (.html):

Describe the HTML structure, template variables, and web-specific rendering context it provides.

If it's a styling file (.css/.scss):

Describe the styling approach, component styles, or global styles for web platform.

List which other files or packages this file is directly coupled with, either through imports, widget usage, or function dependencies.

Mention any external packages, Flutter SDK, or third-party libraries (e.g., flutter/material.dart, provider, bloc, dio, shared_preferences) used here.

Response Format:

Return only the raw description text (no markdown, bullets, or headings).

Do not include any code or formatting artifacts
    """

    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents = prompt
    )

    return resp.text

def generate_file_content(context: str, filepath: str, refined_prompt: str, tree: str, json_file_name: str) -> str:
    
    file_type = os.path.splitext(filepath)[1]
    filename = os.path.basename(filepath)
    
    prompt = f"""Generate the content of a Flutter project file.

Details:

File Name: {filename}

File Type: {file_type} (e.g., Dart, YAML, JSON, XML, Gradle, Kotlin, Swift, HTML, CSS)

Project Context: {context} (e.g., lib/screens/, lib/widgets/, lib/models/, lib/services/, lib/providers/, lib/utils/, assets/, android/, ios/, web/)

Project Idea: {refined_prompt}

Full Folder Structure: {tree}

Requirements:

Follow Flutter and Dart best practices relevant to the file type

Include only necessary imports or dependencies

Use documentation comments and inline comments for clarity where applicable

For Dart files (.dart):

Use proper Dart conventions with clear library declarations

Include comprehensive class definitions and method documentation

Add dartdoc comments for public APIs and widgets

Follow Dart naming conventions and Flutter project structure

Implement proper error handling and state management

Use Flutter framework features and widgets appropriately

Follow widget composition and lifecycle best practices

For Configuration files (pubspec.yaml):

Use proper Flutter SDK versioning and dependency management

Include all necessary dependencies with appropriate versions

Configure proper package name and Flutter version requirements

Set up assets, fonts, and platform-specific configurations

Follow Flutter package management best practices

For Platform-specific files (.gradle/.kt/.swift/.xml):

Include all necessary platform configurations and permissions

Configure proper build settings and native integrations

Set up deployment and signing configurations

Configure development and production environment separation

Follow platform-specific best practices (Android/iOS)

For Asset configuration files (.json):

Include all necessary application settings and parameters

Configure proper localization and internationalization

Set up app configuration and feature flags

Configure API endpoints and environment variables

Set up analytics and crash reporting configurations

For Template files (.html):

Write clean, semantic HTML with proper Flutter web integration

Use modern HTML5 standards and accessibility guidelines

Include proper meta tags and responsive design elements

Implement proper Flutter web app shell structure

Follow progressive web app (PWA) best practices

For Styling files (.css/.scss):

Write modular, reusable styles with proper organization

Follow modern CSS practices and naming conventions

Ensure responsive design and cross-platform compatibility

Use CSS custom properties and modern features

Implement proper component scoping for Flutter web

For Screen/Widget files:

Write clean, reusable widgets with proper state management

Use Flutter context and navigation appropriately

Include comprehensive error handling and loading states

Add proper widget lifecycle management

Follow Material Design or Cupertino design principles

For Service files:

Write clean API integration with proper error handling

Use proper HTTP client configuration and interceptors

Include comprehensive data serialization and validation

Add proper caching and offline support

Follow repository pattern and dependency injection

For Model files:

Write clean data models with proper serialization

Use proper Dart class conventions and immutability

Include comprehensive validation and type safety

Add proper JSON serialization annotations

Follow data transfer object (DTO) patterns

For Provider/State Management files:

Write clean state management with proper separation of concerns

Use appropriate state management solution (Provider, Bloc, Riverpod)

Include comprehensive state transitions and error handling

Add proper dependency injection and testing support

Follow state management best practices and patterns

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
    You are an expert Flutter code reviewer.

You are reviewing the coupling accuracy of a Flutter file by comparing:

The actual imports, dependencies, and logical usage in the file

The declared couples_with list in the project's metadata

The dependencies extracted via static analysis

Your goal is to verify whether the declared couplings are complete, precise, and consistent with the file's true behavior.

File Path: {file_path}

File Content:
{file_content}

Declared Metadata Couplings (couples_with):
{metadata_dict.get('couples_with', [])}

Statically Detected Dependencies (from code analysis):
{actual_dependencies}

Instructions
Analyze the file's actual import statements, package usage, widget references, and cross-module dependencies.

For Dart files: Check import statements, widget usage, class references, function calls, and package dependencies.

For Configuration files (pubspec.yaml): Check dependency declarations, asset configurations, and Flutter SDK constraints.

For Platform-specific files (.gradle/.kt/.swift/.xml): Check dependency declarations, native integrations, and build configurations.

For Asset configuration files (.json): Check configuration references, localization keys, and external service integrations.

For Template files (.html): Check script includes, stylesheet references, and asset dependencies.

For Styling files (.css/.scss): Check @import statements, CSS custom properties, and component style dependencies.

Compare that to the declared couplings in the metadata (couples_with).

Then compare both with the dependencies inferred via static analysis (actual_dependencies).

If you find discrepancies, please describe the issue and suggest corrections.

Determine if:
All couplings in the code are properly captured in the metadata

There are any incorrect, missing, or extra entries in the metadata

Any syntactical or logical errors in the file that prevent it from compiling or running correctly

Return Format
Return ONLY this exact JSON format:
{
"correctness": "correct" or "incorrect",
"changes_needed": "clear explanation of what's missing, extra, or incorrect (empty string if everything is accurate)"
}
Examples
Example 1 (Correct):
{
"correctness": "correct",
"changes_needed": ""
}
Example 2 (Incorrect):
{
"correctness": "incorrect",
"changes_needed": "The file imports package:flutter/material.dart but flutter/material.dart is missing in the declared metadata. Also, metadata lists provider package but it should be package:provider/provider.dart as the actual import. The file also uses UserModel class from models package but lib/models/user_model.dart is not captured in the metadata. The file references assets/images/logo.png but this asset dependency is not listed in couples_with."
}
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
    
    if file_ext == '.dart':
        import_pattern = r'import\s+[\'"]([^\'"]+)[\'"]'
        export_pattern = r'export\s+[\'"]([^\'"]+)[\'"]'
        part_pattern = r'part\s+[\'"]([^\'"]+)[\'"]'
        part_of_pattern = r'part\s+of\s+[\'"]([^\'"]+)[\'"]'
        class_pattern = r'class\s+([A-Z][a-zA-Z0-9]*)'
        widget_pattern = r'([A-Z][a-zA-Z0-9]*Widget|[A-Z][a-zA-Z0-9]*Screen|[A-Z][a-zA-Z0-9]*Page)'
        
        import_matches = re.findall(import_pattern, content)
        export_matches = re.findall(export_pattern, content)
        part_matches = re.findall(part_pattern, content)
        part_of_matches = re.findall(part_of_pattern, content)
        class_matches = re.findall(class_pattern, content)
        widget_matches = re.findall(widget_pattern, content)
        
        all_imports = import_matches + export_matches + part_matches + part_of_matches
        
        for imp in all_imports:
            if imp.startswith('./') or imp.startswith('../'):
                file_dir = os.path.dirname(file_path)
                resolved_path = os.path.normpath(os.path.join(file_dir, imp))
                
                potential_files = [
                    resolved_path,
                    resolved_path + '.dart',
                    os.path.join(resolved_path, 'main.dart'),
                    os.path.join(resolved_path, 'index.dart')
                ]
                
                if not any(pf in project_files for pf in potential_files):
                    invalid_imports.append(f"Local import '{imp}' in {file_path} does not exist")
            
            elif imp.startswith('package:'):
                package_name = imp.split('/')[0].replace('package:', '')
                pubspec_path = 'pubspec.yaml'
                if pubspec_path in project_files:
                    try:
                        with open(pubspec_path, 'r') as f:
                            pubspec_content = f.read()
                        if package_name not in pubspec_content and not any(package_name.startswith(builtin) for builtin in [
                            'flutter', 'dart'
                        ]):
                            invalid_imports.append(f"Dart package '{package_name}' not found in pubspec.yaml dependencies")
                    except:
                        pass
            
            elif not imp.startswith('dart:') and not any(imp.startswith(builtin) for builtin in [
                'flutter/', 'package:flutter'
            ]):
                lib_path = f"lib/{imp}"
                if lib_path + '.dart' not in project_files and lib_path not in project_files:
                    invalid_imports.append(f"Local library '{imp}' not found in lib directory")
        
        for class_name in class_matches:
            class_files = [
                f"lib/models/{class_name.lower()}.dart",
                f"lib/widgets/{class_name.lower()}.dart",
                f"lib/screens/{class_name.lower()}.dart",
                f"lib/services/{class_name.lower()}.dart"
            ]
            if not any(cf in project_files for cf in class_files):
                invalid_imports.append(f"Class '{class_name}' in {file_path} may not exist in expected locations")
    
    elif file_ext == '.yaml' and 'pubspec' in file_path:
        try:
            import yaml
            yaml_data = yaml.safe_load(content)
            
            if isinstance(yaml_data, dict):
                if 'flutter' in yaml_data and 'assets' in yaml_data['flutter']:
                    for asset in yaml_data['flutter']['assets']:
                        if asset not in project_files and not asset.endswith('/'):
                            invalid_imports.append(f"Asset '{asset}' declared in pubspec.yaml does not exist")
                
                if 'flutter' in yaml_data and 'fonts' in yaml_data['flutter']:
                    for font_family in yaml_data['flutter']['fonts']:
                        if 'fonts' in font_family:
                            for font in font_family['fonts']:
                                if 'asset' in font and font['asset'] not in project_files:
                                    invalid_imports.append(f"Font asset '{font['asset']}' does not exist")
                                    
        except Exception:
            pass
    
    elif file_ext == '.gradle':
        implementation_pattern = r'implementation\s+[\'"]([^\'"]+)[\'"]'
        api_pattern = r'api\s+[\'"]([^\'"]+)[\'"]'
        plugin_pattern = r'apply\s+plugin:\s*[\'"]([^\'"]+)[\'"]'
        
        implementation_matches = re.findall(implementation_pattern, content)
        api_matches = re.findall(api_pattern, content)
        plugin_matches = re.findall(plugin_pattern, content)
        
        for dep in implementation_matches + api_matches:
            if dep.startswith('project('):
                project_path = dep.replace('project(', '').replace(')', '').replace('\'', '').replace('"', '')
                if project_path.startswith(':'):
                    project_path = project_path[1:]
                gradle_file = f"{project_path}/build.gradle"
                if gradle_file not in project_files:
                    invalid_imports.append(f"Gradle project dependency '{project_path}' does not exist")
    
    elif file_ext == '.kt':
        import_pattern = r'import\s+([^\s]+)'
        class_pattern = r'class\s+([A-Z][a-zA-Z0-9]*)'
        
        import_matches = re.findall(import_pattern, content)
        class_matches = re.findall(class_pattern, content)
        
        for imp in import_matches:
            if imp.startswith('com.') and 'flutter' in imp:
                continue
            elif not any(imp.startswith(android_pkg) for android_pkg in [
                'android.', 'androidx.', 'kotlin.', 'java.', 'javax.'
            ]):
                kt_file = imp.replace('.', '/') + '.kt'
                if kt_file not in project_files:
                    invalid_imports.append(f"Kotlin import '{imp}' may not exist")
    
    elif file_ext == '.swift':
        import_pattern = r'import\s+([^\s]+)'
        class_pattern = r'class\s+([A-Z][a-zA-Z0-9]*)'
        
        import_matches = re.findall(import_pattern, content)
        class_matches = re.findall(class_pattern, content)
        
        for imp in import_matches:
            if not any(imp.startswith(ios_framework) for ios_framework in [
                'UIKit', 'Foundation', 'CoreData', 'Flutter'
            ]):
                swift_file = f"{imp}.swift"
                if swift_file not in project_files:
                    invalid_imports.append(f"Swift import '{imp}' may not exist")
    
    elif file_ext == '.xml':
        if 'AndroidManifest.xml' in file_path:
            activity_pattern = r'<activity[^>]+android:name=[\'"]([^\'"]+)[\'"]'
            service_pattern = r'<service[^>]+android:name=[\'"]([^\'"]+)[\'"]'
            receiver_pattern = r'<receiver[^>]+android:name=[\'"]([^\'"]+)[\'"]'
            
            activity_matches = re.findall(activity_pattern, content)
            service_matches = re.findall(service_pattern, content)
            receiver_matches = re.findall(receiver_pattern, content)
            
            for activity in activity_matches:
                if activity.startswith('.'):
                    kt_file = f"android/app/src/main/kotlin/{activity[1:].replace('.', '/')}.kt"
                    if kt_file not in project_files:
                        invalid_imports.append(f"Activity '{activity}' does not exist")
        
        drawable_pattern = r'@drawable/([a-zA-Z0-9_]+)'
        string_pattern = r'@string/([a-zA-Z0-9_]+)'
        color_pattern = r'@color/([a-zA-Z0-9_]+)'
        
        drawable_matches = re.findall(drawable_pattern, content)
        string_matches = re.findall(string_pattern, content)
        color_matches = re.findall(color_pattern, content)
        
        for drawable in drawable_matches:
            drawable_files = [
                f"android/app/src/main/res/drawable/{drawable}.xml",
                f"android/app/src/main/res/drawable/{drawable}.png",
                f"android/app/src/main/res/drawable/{drawable}.jpg"
            ]
            if not any(df in project_files for df in drawable_files):
                invalid_imports.append(f"Drawable resource '{drawable}' does not exist")
    
    elif file_ext == '.json':
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
    
    elif file_ext in ['.html']:
        script_pattern = r'<script[^>]+src=[\'"]([^\'"]+)[\'"]'
        link_pattern = r'<link[^>]+href=[\'"]([^\'"]+)[\'"]'
        img_pattern = r'<img[^>]+src=[\'"]([^\'"]+)[\'"]'
        
        script_matches = re.findall(script_pattern, content)
        link_matches = re.findall(link_pattern, content)
        img_matches = re.findall(img_pattern, content)
        
        for script_src in script_matches:
            if not script_src.startswith('http') and not script_src.startswith('//'):
                if script_src.startswith('/'):
                    web_path = 'web' + script_src
                    if web_path not in project_files:
                        invalid_imports.append(f"Script source '{script_src}' does not exist in web folder")
                elif script_src not in project_files:
                    invalid_imports.append(f"Script source '{script_src}' does not exist")
        
        for link_href in link_matches:
            if not link_href.startswith('http') and not link_href.startswith('//'):
                if link_href.startswith('/'):
                    web_path = 'web' + link_href
                    if web_path not in project_files:
                        invalid_imports.append(f"Link href '{link_href}' does not exist in web folder")
                elif link_href not in project_files:
                    invalid_imports.append(f"Link href '{link_href}' does not exist")
        
        for img_src in img_matches:
            if not img_src.startswith('http') and not img_src.startswith('data:'):
                if img_src.startswith('/'):
                    web_path = 'web' + img_src
                    assets_path = 'assets' + img_src
                    if web_path not in project_files and assets_path not in project_files:
                        invalid_imports.append(f"Image source '{img_src}' does not exist")
    
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
                    invalid_imports.append(f"Style import '{style_import}' does not exist")
        
        for url_ref in url_matches:
            if not url_ref.startswith('http') and not url_ref.startswith('data:') and not url_ref.startswith('//'):
                if url_ref.startswith('/'):
                    web_path = 'web' + url_ref
                    assets_path = 'assets' + url_ref
                    if web_path not in project_files and assets_path not in project_files:
                        invalid_imports.append(f"CSS URL reference '{url_ref}' does not exist")
    
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
    You are an expert Flutter developer.

Your task is to correct the following Flutter project file so that its imports, dependencies, and references properly match the declared couplings and dependency expectations, based on feedback from a static analysis and metadata validation.

Original File Content:
{file_content}

Correction Feedback:
{changes_needed}

Requirements
Fix only the issues mentioned in the Correction Feedback — including:

Missing or incorrect import statements and package references:

Dart import statements (import 'package:' or relative imports)

Widget and class references from other files

Asset references and path corrections

Imports of non-existent packages, widgets, models, or services — these should be removed:

Remove imports to files that don't exist in the project

Remove unused package dependencies

Remove references to non-existent widgets or classes

Typographical errors in import statements, package names, or function names:

Correct misspelled package names

Fix incorrect widget or class names

Correct asset path typos

Syntactical errors in the file that prevent it from compiling correctly:

Fix Dart syntax errors

Correct widget composition issues

Fix state management syntax

Missing package dependencies in pubspec.yaml files:

Add missing dependencies to pubspec.yaml

Correct version constraints

Fix asset declarations

Incorrect widget references or function usage:

Fix widget constructor calls

Correct method invocations

Fix state management references

Missing or incorrect Dart/Flutter imports:

Add missing Flutter framework imports

Correct Dart core library imports

Fix third-party package imports

Ensure that all imports and references are logically correct and semantically aligned with the metadata.

If an import statement is missing, add it.
If an import statement is incorrect, correct it.
If an import statement is redundant or not used, remove it.
If an import references a package/file that does not exist in the project, remove or replace it as appropriate.

For Dart files: ensure proper package imports and widget/class usage.
For Configuration files (pubspec.yaml): ensure proper dependency declarations and versions.
For Platform-specific files: ensure proper native configurations and settings.
For Asset files: ensure proper asset references and paths.

Do not:
Add any new functionality unrelated to the correction

Modify logic outside of the specified corrections

Introduce any new widgets, models, or services beyond what's mentioned

Change the overall architecture or design patterns

Maintain original indentation, code structure, and Flutter best practices.

Output Format
Return the corrected file content as raw code (Dart, YAML, JSON, XML, Gradle, Kotlin, Swift, etc.).

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
