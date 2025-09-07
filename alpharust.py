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
    '.rs', '.toml', '.html', '.css', '.js', '.ts', '.tsx', '.jsx', '.json', 
    '.md', '.yml', '.yaml', '.env', '.txt', '.png', '.ico', '.sh', '.so'
}

GENERATABLE_FILENAMES = {
    'Cargo.toml', 'Anchor.toml', 'lib.rs', 'main.rs', 'mod.rs', 'Dockerfile', 
    'README.md', '.gitignore', 'package.json', 'tsconfig.json', '.env'
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
        
        if file_path.endswith(".rs"):
            use_statements = re.findall(r'use\s+([^;]+);', content)
            for use_stmt in use_statements:
                if use_stmt.startswith('crate::'):
                    dependencies.add(use_stmt.replace('crate::', ''))
                elif '::' in use_stmt:
                    crate_name = use_stmt.split('::')[0]
                    dependencies.add(crate_name)
                else:
                    dependencies.add(use_stmt)
            
            mod_statements = re.findall(r'mod\s+([a-zA-Z_][a-zA-Z0-9_]*);', content)
            for mod_name in mod_statements:
                mod_file = os.path.join(file_dir, f"{mod_name}.rs")
                if os.path.exists(mod_file):
                    dependencies.add(mod_file)
                else:
                    mod_dir_file = os.path.join(file_dir, mod_name, "mod.rs")
                    if os.path.exists(mod_dir_file):
                        dependencies.add(mod_dir_file)

        elif file_path.endswith(".toml"):
            try:
                toml_data = toml.loads(content)
                
                if 'dependencies' in toml_data:
                    for dep_name in toml_data['dependencies'].keys():
                        dependencies.add(dep_name)
                
                if 'dev-dependencies' in toml_data:
                    for dep_name in toml_data['dev-dependencies'].keys():
                        dependencies.add(dep_name)
                
                if 'build-dependencies' in toml_data:
                    for dep_name in toml_data['build-dependencies'].keys():
                        dependencies.add(dep_name)
                        
            except Exception as e:
                print(f"Error parsing TOML {file_path}: {e}")

        elif file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            import_statements = re.findall(r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in import_statements:
                dependencies.add(imp)
            
            require_statements = re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', content)
            for req in require_statements:
                dependencies.add(req)

        elif file_path.endswith(".json"):
            try:
                import json
                json_data = json.loads(content)
                
                if 'dependencies' in json_data:
                    for dep_name in json_data['dependencies'].keys():
                        dependencies.add(dep_name)
                
                if 'devDependencies' in json_data:
                    for dep_name in json_data['devDependencies'].keys():
                        dependencies.add(dep_name)
                        
            except Exception as e:
                print(f"Error parsing JSON {file_path}: {e}")

        elif file_path.endswith(".html"):
            includes = re.findall(r'{%\s*(include|extends)\s+[\'"]([^\'"]+)[\'"]\s*%}', content)
            for _, template in includes:
                dependencies.add(template)
            
            scripts = re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', content)
            for script in scripts:
                dependencies.add(script)
            
            links = re.findall(r'<link[^>]+href=[\'"]([^\'"]+)[\'"]', content)
            for link in links:
                dependencies.add(link)
            
        elif file_path.endswith(".css"):
            imports = re.findall(r'@import\s+[\'"]([^\'"]+)[\'"]', content)
            for imp in imports:
                dependencies.add(imp)
        
        return dependencies
    
    def resolve_rust_module(self, file_dir: str, mod_name: str) :
        mod_file = os.path.join(file_dir, f"{mod_name}.rs")
        if os.path.exists(mod_file):
            return mod_file
        
        mod_dir_file = os.path.join(file_dir, mod_name, "mod.rs")
        if os.path.exists(mod_dir_file):
            return mod_dir_file
        
        return None
    
    def get_dependencies(self, file_path: str) -> List[str]:
        return list(self.graph.successors(file_path))
    
    def get_dependents(self, file_path: str) -> List[str]:
        return list(self.graph.predecessors(file_path))
    
    def get_all_nodes(self) -> List[str]:
        return list(self.graph.nodes)
    
    def get_rust_crates(self):
        crates = set()
        for node in self.graph.nodes:
            if node.endswith(".toml"):
                for dep in self.get_dependencies(node):
                    if not dep.startswith('./') and not dep.endswith('.rs'):
                        crates.add(dep)
        return crates
    
    def visualize_graph(self):
        try:
            import matplotlib.pyplot as plt
            pos = nx.spring_layout(self.graph)
            nx.draw(self.graph, pos, with_labels=True, arrows=True, 
                   node_size=2000, node_color='lightblue', 
                   font_size=8, font_color='black', edge_color='gray')
            plt.title("Rust Solana dApp Dependency Graph")
            plt.show()
        except ImportError:
            print("Matplotlib is not installed. Skipping graph visualization.")

def refine_prompt(prompt: string) ->  string:
    resp = genai.GenerativeModel("gemini-2.5-flash-preview-05-20").generate_content(
        contents = f"""
            You are a senior Rust Solana dApp architect. Your task is to take a high-level project idea and generate a detailed prompt that instructs a language model to output a production-ready Rust Solana dApp folder structure, including all directories and file names, but no file contents or code.

Analyse the {prompt} first—if it lacks clarity or scope, elaborate on it appropriately before proceeding. If the prompt is already detailed, return it as is.

project_name : {prompt}

Follow these rules when writing the refined prompt:
Prompt Template to Generate:
Project Name : 

Generate the folder structure only (no code or file contents) for a Rust Solana dApp project named .

This project is a , with the following key features:





Use Rust Solana dApp best practices:

Modular, reusable program structure with clear separation of concerns.

Strictly include Cargo.toml in the root directory to manage dependencies.

Follow the standard Anchor framework layout for production-grade Solana programs.

Include standard folders and files for:

On-chain program: programs/

Client-side application: app/

Tests: tests/

Deployment scripts: scripts/

Configuration: Anchor.toml

The program modules should include, but are not limited to:

instructions – handles all program instructions and business logic.

state – defines account structures and program state.

errors – custom error definitions for the program.

utils – shared utilities and helper functions.

Follow Rust and Solana naming conventions and proper project structuring.

Return only the folder structure with relevant file names in a tree view format.
Do not include any code or file contents.

Additional Technical Requirements & Best Practices:
Maintain modularity and reusability across all program modules.

Use a standard Anchor production layout:

Root project directory with Cargo.toml and Anchor.toml

Programs directory containing the Solana program source code

App directory for frontend client application

Tests directory for integration and unit tests

Scripts directory for deployment and utility scripts

Include package.json, .env.example, .env, README.md, .gitignore

Placeholders for deployment: Dockerfile, docker-compose.yml, .github/workflows/, etc.

Each program should have: src/lib.rs, src/instructions/, src/state/, src/errors.rs

The app/ folder must contain TypeScript/React frontend with proper component structure

📌 Front-End Development Guidelines:
Use TypeScript for all client-side development. All TypeScript logic must reside in properly typed .ts/.tsx files organized under the app/src/ directory.

Leverage modern React framework with proper component architecture. Include React components in app/src/components/ with clear separation of concerns.

Use Solana web3.js and Anchor client libraries for blockchain interaction. Organize wallet adapters and program interactions in dedicated service files.

Ensure frontend properly handles wallet connections, transaction signing, and program interactions through well-structured service layers.

Example Input:
Input: decentralized voting platform

Expected Refined Prompt Output:
Project Name : decentralized_voting_platform

Generate the folder structure only (no code or file contents) for a Rust Solana dApp project named decentralized_voting_platform.

The project is a Decentralized Voting Platform with the following key features:

Users can connect wallets and participate in voting campaigns.

Campaign creators can initialize voting campaigns with custom parameters.

Voters can cast votes on active campaigns.

Real-time vote tallying and results display.

User Roles and Capabilities:

Voters: Connect wallet, view campaigns, cast votes, and view results.

Campaign Creators: Initialize campaigns, set voting parameters, and manage campaign lifecycle.

Admins: Oversee platform governance and manage campaign validation.

Use Rust Solana dApp best practices:

Structure the project with modular Anchor program architecture.

Separate on-chain logic from client-side application code.

Use TypeScript for all frontend development with proper typing.

Implement proper wallet integration and transaction handling.

Follow standard Anchor production layout with clear program boundaries.

Include folders for:

programs/

app/

tests/

scripts/

Program modules to include:

instructions

state

errors

utils

Include standard Rust/Solana files such as:

Cargo.toml and Anchor.toml in the root

lib.rs, instructions/mod.rs, state/mod.rs, errors.rs in the program

package.json, tsconfig.json in the app directory

Integration tests in tests/ directory

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

    prompt = f"""You are analyzing a file from a Rust Solana dApp project. Generate a detailed yet concise metadata description that captures its purpose, structure, and relationships.

**File Information**
- File Name: {filename}
- File Type: {file_type} (e.g., .rs, .ts, .tsx, .toml, .json)
- Project Location: {context} (e.g., programs/src/instructions, app/src/components, tests/)
- Project Idea: {refined_prompt}
- Project Structure:
{tree}
- File Content:
{file_content}

**What to include in your response:**
1. A concise 2–3 sentence summary of what this file does and how it fits into the Rust Solana dApp project.
2. If it's a Rust file (.rs):
- Mention key structs, functions, instructions, account definitions, or error types.
3. If it's a TypeScript/React file (.ts/.tsx):
- Describe the component, service, or utility it provides and any React hooks or context usage.
4. If it's a configuration file (.toml/.json):
- Explain the dependencies, build settings, or project configuration it manages.
5. List **which other files or modules this file is directly coupled with**, either through imports, usage, or program interactions.
6. Mention any external crates, Solana/Anchor frameworks, or web3 libraries (e.g., `anchor-lang`, `@solana/web3.js`, `@project-serum/anchor`) used here.

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
    
    prompt = f"""Generate the content of a Rust Solana dApp project file.

Details:
- File Name: {filename}
- File Type: {file_type} (e.g., Rust, TypeScript, TOML, JSON, HTML, CSS)
- Project Context: {context} (e.g., programs/src/instructions, app/src/components, tests/, scripts/, etc.)
- Project Idea: {refined_prompt}
- Full Folder Structure: {tree}

Requirements:
- Follow Rust Solana dApp best practices relevant to the file type
- Include only necessary imports or dependencies
- Use documentation comments and inline comments for clarity where applicable

For Rust files (.rs):
- Use proper Anchor framework patterns and macros
- Include comprehensive error handling
- Add documentation comments for public functions and structs
- Follow Rust naming conventions and ownership patterns
- Implement proper account validation and security checks

For TypeScript/React files (.ts/.tsx):
- Use proper TypeScript typing throughout
- Implement React best practices with hooks and functional components
- Include proper wallet integration and transaction handling
- Use Solana web3.js and Anchor client libraries appropriately
- Add error boundaries and loading states

For Configuration files (.toml/.json):
- Include all necessary dependencies and their appropriate versions
- Configure proper build settings and deployment parameters
- Set up development and production environment variables

For HTML template files:
- Write clean, semantic HTML
- Avoid inline JavaScript
- Include proper meta tags and accessibility features
- Use responsive design principles

For CSS files:
- Write modular, reusable styles
- Follow modern CSS practices and naming conventions
- Ensure responsive design and cross-browser compatibility
- Use CSS custom properties where appropriate

For JavaScript files:
- Write clean, modular code following ES6+ standards
- Use proper async/await patterns for blockchain interactions
- Include comprehensive error handling
- Add JSDoc comments for clarity

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
    You are an expert Rust Solana dApp code reviewer.

You are reviewing the coupling accuracy of a Rust Solana dApp file by comparing:
1. The actual imports, dependencies, and logical usage in the file.
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
- Analyze the file's actual use statements, crate imports, module references, and cross-program/component usage.
- For Rust files: Check `use` statements, `mod` declarations, external crate usage, and Anchor program interactions.
- For TypeScript files: Check `import` statements, component references, and Solana/Anchor client library usage.
- For configuration files: Check dependency declarations and build configurations.
- Compare that to the declared couplings in the metadata (`couples_with`).
- Then compare both with the dependencies inferred via static analysis (`actual_dependencies`).
- If you find discrepancies, please describe the issue and suggest corrections.
- Determine if:
1. All couplings in the code are properly captured in the metadata.
2. There are any incorrect, missing, or extra entries in the metadata.
3. Any syntactical or logical errors in the file that prevent it from compiling or running correctly.

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

Example 2 (Incorrect):
{{
"correctness": "incorrect",
"changes_needed": "The file imports `use crate::state::VotingAccount` but `state` module is missing in the declared metadata. Also, metadata lists `anchor_lang::prelude` but it should be `anchor_lang` as the actual import. The file also uses `@solana/web3.js` library but this dependency is not captured in the metadata."
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
    
    if file_ext == '.rs':
        use_pattern = r'use\s+([^;]+);'
        mod_pattern = r'mod\s+([a-zA-Z_][a-zA-Z0-9_]*);'
        
        use_matches = re.findall(use_pattern, content)
        for use_stmt in use_matches:
            use_stmt = use_stmt.strip()
            
            if use_stmt.startswith('crate::'):
                module_path = use_stmt.replace('crate::', '').split('::')[0]
                potential_files = [
                    f"src/{module_path}.rs",
                    f"src/{module_path}/mod.rs"
                ]
                if not any(pf in project_files for pf in potential_files):
                    invalid_imports.append(f"Rust module '{module_path}' in {file_path} does not exist")
            
            elif use_stmt.startswith('super::'):
                parent_dir = os.path.dirname(file_path)
                if parent_dir:
                    parent_parent = os.path.dirname(parent_dir)
                    module_name = use_stmt.replace('super::', '').split('::')[0]
                    potential_file = os.path.join(parent_parent, f"{module_name}.rs")
                    if potential_file not in project_files:
                        invalid_imports.append(f"Super module '{module_name}' in {file_path} does not exist")
            
            elif '::' in use_stmt and not any(use_stmt.startswith(external) for external in [
                'anchor_lang', 'solana_program', 'spl_token', 'borsh', 'std', 'core', 'alloc'
            ]):
                crate_name = use_stmt.split('::')[0]
                cargo_toml_path = 'Cargo.toml'
                if cargo_toml_path in project_files:
                    try:
                        with open(cargo_toml_path, 'r') as f:
                            cargo_content = f.read()
                        if f'"{crate_name}"' not in cargo_content and f"'{crate_name}'" not in cargo_content:
                            invalid_imports.append(f"External crate '{crate_name}' not found in Cargo.toml dependencies")
                    except:
                        pass
        
        mod_matches = re.findall(mod_pattern, content)
        for mod_name in mod_matches:
            file_dir = os.path.dirname(file_path)
            potential_files = [
                os.path.join(file_dir, f"{mod_name}.rs"),
                os.path.join(file_dir, mod_name, "mod.rs")
            ]
            if not any(pf in project_files for pf in potential_files):
                invalid_imports.append(f"Module '{mod_name}' in {file_path} does not exist")
    
    elif file_ext in ['.ts', '.tsx', '.js', '.jsx']:
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
        require_pattern = r'require\([\'"]([^\'"]+)[\'"]\)'
        
        import_matches = re.findall(import_pattern, content)
        require_matches = re.findall(require_pattern, content)
        
        all_imports = import_matches + require_matches
        
        for imp in all_imports:
            if imp.startswith('./') or imp.startswith('../'):
                file_dir = os.path.dirname(file_path)
                resolved_path = os.path.normpath(os.path.join(file_dir, imp))
                
                potential_files = [
                    resolved_path,
                    resolved_path + '.ts',
                    resolved_path + '.tsx',
                    resolved_path + '.js',
                    resolved_path + '.jsx',
                    os.path.join(resolved_path, 'index.ts'),
                    os.path.join(resolved_path, 'index.tsx'),
                    os.path.join(resolved_path, 'index.js'),
                    os.path.join(resolved_path, 'index.jsx')
                ]
                
                if not any(pf in project_files for pf in potential_files):
                    invalid_imports.append(f"Local import '{imp}' in {file_path} does not exist")
            
            elif not any(imp.startswith(external) for external in [
                '@solana/', '@project-serum/', 'react', 'next', 'typescript', 'node:', 'buffer', 'crypto'
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
    
    elif file_ext == '.toml':
        if 'Cargo.toml' in file_path:
            try:
                toml_data = toml.loads(content)
                
                if 'dependencies' in toml_data:
                    for dep_name, dep_config in toml_data['dependencies'].items():
                        if isinstance(dep_config, dict) and 'path' in dep_config:
                            dep_path = dep_config['path']
                            cargo_path = os.path.join(dep_path, 'Cargo.toml')
                            if cargo_path not in project_files:
                                invalid_imports.append(f"Local dependency path '{dep_path}' in Cargo.toml does not exist")
                
                if 'workspace' in toml_data and 'members' in toml_data['workspace']:
                    for member in toml_data['workspace']['members']:
                        member_cargo = os.path.join(member, 'Cargo.toml')
                        if member_cargo not in project_files:
                            invalid_imports.append(f"Workspace member '{member}' does not exist")
                            
            except Exception:
                pass
        
        elif 'Anchor.toml' in file_path:
            try:
                toml_data = toml.loads(content)
                
                if 'programs' in toml_data and 'localnet' in toml_data['programs']:
                    for program_name, program_path in toml_data['programs']['localnet'].items():
                        target_dir = os.path.join('target', 'deploy')
                        so_file = os.path.join(target_dir, f"{program_name}.so")
                        
                if 'test' in toml_data and 'validator' in toml_data['test']:
                    validator_config = toml_data['test']['validator']
                    if 'clone' in validator_config:
                        for clone_config in validator_config['clone']:
                            if 'address' in clone_config and len(clone_config['address']) != 44:
                                invalid_imports.append(f"Invalid Solana address in Anchor.toml clone configuration")
                                
            except Exception:
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
        
        elif 'tsconfig.json' in file_path:
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
    
    elif file_ext == '.html':
        script_pattern = r'<script[^>]+src=[\'"]([^\'"]+)[\'"]'
        link_pattern = r'<link[^>]+href=[\'"]([^\'"]+)[\'"]'
        
        script_matches = re.findall(script_pattern, content)
        link_matches = re.findall(link_pattern, content)
        
        for script_src in script_matches:
            if not script_src.startswith('http') and not script_src.startswith('//'):
                if script_src not in project_files:
                    invalid_imports.append(f"Script source '{script_src}' in {file_path} does not exist")
        
        for link_href in link_matches:
            if not link_href.startswith('http') and not link_href.startswith('//'):
                if link_href not in project_files:
                    invalid_imports.append(f"Link href '{link_href}' in {file_path} does not exist")
    
    elif file_ext == '.css':
        import_pattern = r'@import\s+[\'"]([^\'"]+)[\'"]'
        url_pattern = r'url\([\'"]?([^\'"]+)[\'"]?\)'
        
        import_matches = re.findall(import_pattern, content)
        url_matches = re.findall(url_pattern, content)
        
        for css_import in import_matches:
            if not css_import.startswith('http') and css_import not in project_files:
                invalid_imports.append(f"CSS import '{css_import}' in {file_path} does not exist")
        
        for url_ref in url_matches:
            if not url_ref.startswith('http') and not url_ref.startswith('data:'):
                if url_ref not in project_files:
                    invalid_imports.append(f"CSS URL reference '{url_ref}' in {file_path} does not exist")
    
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
    You are an expert Rust Solana dApp developer.

Your task is to correct the following Rust Solana dApp project file so that its **imports, dependencies, and references** properly match the declared couplings and dependency expectations, based on feedback from a static analysis and metadata validation.

---

**Original File Content**:
{file_content}

---

**Correction Feedback**:
{changes_needed}

---

**Requirements**:
- Fix **only the issues mentioned in the Correction Feedback** — including:
    - Missing or incorrect `use` statements and imports.
    - Imports of non-existent crates, modules, or files — these should be removed.
    - Typographical errors in import statements, struct names, or function names.
    - Syntactical errors in the file that prevent it from compiling correctly.
    - Missing crate dependencies in Cargo.toml or package.json files.
    - Incorrect module declarations or path references.
- Ensure that all imports and references are logically correct and semantically aligned with the metadata.
- If a `use` statement is missing, **add it**.
- If a `use` statement is incorrect, **correct it**.
- If a `use` statement is redundant or not used, **remove it**.
- If an import references a crate/module that does not exist in the project, **remove or replace it** as appropriate.
- For TypeScript files, ensure proper import syntax and library references.
- For configuration files, ensure proper dependency declarations and versions.
- Do **not**:
    - Add any new functionality unrelated to the correction.
    - Modify logic outside of the specified corrections.
    - Introduce any new features or structs beyond what's mentioned.
- Maintain original indentation, code structure, and Rust/Solana best practices.

---

**Output Format**:
- Return the corrected file content as raw code (Rust, TypeScript, TOML, etc.).
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
