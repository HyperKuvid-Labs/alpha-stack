"""
Main Feedback Loop Module
Orchestrates dependency resolution and Docker testing
"""
import os
import json
from typing import Dict, Optional
from pathlib import Path
from folder_tree import DependencyAnalyzer
from dependency_resolver import resolve_dependencies
from docker_testing import run_docker_testing
from prompt_manager import PromptManager


def run_feedback_loop(project_root: str, dependency_analyzer: DependencyAnalyzer,
                     software_blueprint: Dict, folder_structure: str, 
                     file_output_format: Dict, pm: Optional[PromptManager] = None) -> Dict:
    """
    Main feedback loop that runs both dependency resolution and Docker testing
    
    Args:
        project_root: Root directory of the project
        dependency_analyzer: DependencyAnalyzer instance with project files loaded
        software_blueprint: Software blueprint dictionary
        folder_structure: Folder structure string
        file_output_format: File output format dictionary
        pm: Optional PromptManager instance
    
    Returns:
        Dictionary with combined results
    """
    pm = pm or PromptManager(templates_dir="prompts")
    
    results = {
        "dependency_resolution": None,
        "docker_testing": None
    }
    
    # Step 1: Dependency Resolution
    print("\n" + "=" * 80)
    print("STEP 1: Dependency Resolution")
    print("=" * 80)
    results["dependency_resolution"] = resolve_dependencies(
        project_root=project_root,
        dependency_analyzer=dependency_analyzer,
        software_blueprint=software_blueprint,
        folder_structure=folder_structure,
        file_output_format=file_output_format,
        pm=pm
    )
    
    # Step 2: Docker Testing (only if dependency resolution succeeded or partially succeeded)
    print("\n" + "=" * 80)
    print("STEP 2: Docker Testing & CI/CD Pipeline")
    print("=" * 80)
    results["docker_testing"] = run_docker_testing(
        project_root=project_root,
        software_blueprint=software_blueprint,
        folder_structure=folder_structure,
        file_output_format=file_output_format,
        pm=pm
    )
    
    # Overall success
    results["success"] = (
        results["dependency_resolution"].get("success", False) and
        results["docker_testing"].get("success", False)
    )
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dfs_feedback.py <project_root>")
        sys.exit(1)
    
    project_root = sys.argv[1]
    
    if not os.path.exists(project_root):
        print(f"Error: Project root '{project_root}' does not exist")
        sys.exit(1)
    
    software_blueprint = {}
    folder_structure = ""
    file_output_format = {}
    
    from folder_tree import DependencyAnalyzer
    analyzer = DependencyAnalyzer()
    
    skip_extensions = {'.pyc', '.pyo', '.pyd', '.so', '.dylib', '.dll', '.exe', '.bin'}
    skip_dirs = {'__pycache__', '.git', '.vscode', '.idea', 'node_modules', '.pytest_cache'}
    skip_files = {'tempCodeRunnerFile.py'}
    
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip_dirs]
        for file in files:
            if file.startswith('.'):
                continue
            
            if file in skip_files:
                continue
            
            file_ext = Path(file).suffix.lower()
            if file_ext in skip_extensions:
                continue
            
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                analyzer.add_file(file_path, content, "")
            except Exception as e:
                print(f"Skipping file {file_path}: {e}")
    
    result = run_feedback_loop(
        project_root=project_root,
        dependency_analyzer=analyzer,
        software_blueprint=software_blueprint,
        folder_structure=folder_structure,
        file_output_format=file_output_format
    )
    
    print("\n" + "=" * 80)
    print("📊 Final Results:")
    print(json.dumps(result, indent=2))
    print("=" * 80)