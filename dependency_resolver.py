"""
Dependency Resolver Module
Handles dependency analysis and resolution feedback loop
"""
import os
import json
import re
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
from folder_tree import DependencyAnalyzer
from genai_client import get_client
from prompt_manager import PromptManager


class DependencyError:
    """Represents a dependency error"""
    def __init__(self, file_path: str, error_type: str, message: str, 
                 dependency: Optional[str] = None, affected_files: Optional[List[str]] = None):
        self.file_path = file_path
        self.error_type = error_type
        self.message = message
        self.dependency = dependency
        self.affected_files = affected_files or []
    
    def to_dict(self):
        return {
            "file": self.file_path,
            "error_type": self.error_type,
            "message": self.message,
            "dependency": self.dependency,
            "affected_files": self.affected_files
        }
    
    def __repr__(self):
        return f"DependencyError(file={self.file_path}, type={self.error_type}, msg={self.message})"


class DependencyFeedbackLoop:
    """Implements feedback loop for dependency resolution"""
    
    def __init__(self, dependency_analyzer: DependencyAnalyzer, project_root: str, 
                 software_blueprint: Optional[Dict] = None,
                 folder_structure: Optional[str] = None,
                 file_output_format: Optional[Dict] = None,
                 pm: Optional[PromptManager] = None):
        self.dependency_analyzer = dependency_analyzer
        self.project_root = project_root
        self.software_blueprint = software_blueprint or {}
        self.folder_structure = folder_structure or ""
        self.file_output_format = file_output_format or {}
        self.pm = pm or PromptManager(templates_dir="prompts")
        self.max_iterations = 20
        
    def _build_project_structure_tree(self) -> str:
        """Build a tree representation of the actual project structure"""
        lines = []
        
        def build_tree(dir_path, prefix="", is_last=True):
            rel_path = os.path.relpath(dir_path, self.project_root)
            if rel_path == '.':
                dir_name = os.path.basename(self.project_root)
            else:
                dir_name = os.path.basename(dir_path)
            
            if dir_name.startswith('.') and dir_name != '.':
                return
            
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + dir_name + "/")
            
            prefix_add = "    " if is_last else "│   "
            new_prefix = prefix + prefix_add
            
            try:
                entries = sorted(os.listdir(dir_path))
                dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e)) and not e.startswith('.')]
                files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e)) and not e.startswith('.')]
                
                all_entries = dirs + files
                
                for i, entry in enumerate(all_entries):
                    entry_path = os.path.join(dir_path, entry)
                    is_last_entry = (i == len(all_entries) - 1)
                    
                    if os.path.isdir(entry_path):
                        build_tree(entry_path, new_prefix, is_last_entry)
                    else:
                        connector = "└── " if is_last_entry else "├── "
                        lines.append(new_prefix + connector + entry)
            except PermissionError:
                pass
        
        try:
            build_tree(self.project_root)
        except Exception as e:
            lines.append(f"Error building tree: {e}")
        
        return "\n".join(lines)
    
    def walk_project_files(self) -> List[str]:
        """Walk through all files in the project"""
        files = []
        skip_extensions = {'.pyc', '.pyo', '.pyd', '.so', '.dylib', '.dll', '.exe', '.bin'}
        skip_dirs = {'__pycache__', '.git', '.vscode', '.idea', 'node_modules', '.pytest_cache'}
        skip_files = {'tempCodeRunnerFile.py'}
        
        for root, dirs, filenames in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip_dirs]
            
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                
                if filename in skip_files:
                    continue
                
                file_ext = Path(filename).suffix.lower()
                if file_ext in skip_extensions:
                    continue
                
                file_path = os.path.join(root, filename)
                if os.path.isfile(file_path):
                    files.append(os.path.abspath(file_path))
        
        return sorted(files)
    
    def check_file_dependencies(self, file_path: str, fix_immediately: bool = False) -> List[DependencyError]:
        """Check dependencies for a single file"""
        errors = []
        dep_details = self.dependency_analyzer.get_dependency_details(file_path)
        
        if not dep_details:
            print(f"✅ File {os.path.relpath(file_path, self.project_root)} has no dependencies")
            return errors
        
        print(f"🔍 Checking dependencies for {os.path.relpath(file_path, self.project_root)}")
        
        for dep_info in dep_details:
            if dep_info.get("kind") == "internal":
                dep_path = dep_info.get("path")
                raw_dep = dep_info.get("raw", "")
                
                if not dep_path:
                    errors.append(DependencyError(
                        file_path=file_path,
                        error_type="MISSING_PATH",
                        message=f"Dependency '{raw_dep}' resolved to None",
                        dependency=raw_dep
                    ))
                    continue
                
                if not os.path.exists(dep_path):
                    errors.append(DependencyError(
                        file_path=file_path,
                        error_type="FILE_NOT_FOUND",
                        message=f"Dependency file does not exist: {dep_path}",
                        dependency=raw_dep,
                        affected_files=[dep_path]
                    ))
                    continue
                
                print(f"  🔗 Checking coupling: {raw_dep} -> {os.path.relpath(dep_path, self.project_root)}")
                coupling_error = self.check_coupling(file_path, dep_path, raw_dep)
                
                if coupling_error:
                    print(f"  ⚠️  Coupling error found: {coupling_error.error_type} - {coupling_error.message}")
                    errors.append(coupling_error)
                else:
                    print(f"  ✅ Coupling check passed for {raw_dep}")
            elif dep_info.get("kind") == "external":
                print(f"  External dependency: {dep_info.get('raw', 'unknown')}")
        
        return errors
    
    def check_coupling(self, source_file: str, target_file: str, dependency: str) -> Optional[DependencyError]:
        """Check if source file correctly couples with target file"""
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                source_content = f.read()
            
            with open(target_file, 'r', encoding='utf-8') as f:
                target_content = f.read()
            
            return self._agent_check_coupling(source_file, target_file, source_content, target_content, dependency)
        except Exception as e:
            return DependencyError(
                file_path=source_file,
                error_type="COUPLING_CHECK_ERROR",
                message=f"Error checking coupling: {str(e)}",
                dependency=dependency,
                affected_files=[target_file]
            )
    
    def _agent_check_coupling(self, source_file: str, target_file: str, 
                              source_content: str, target_content: str, 
                              dependency: str) -> Optional[DependencyError]:
        """Use AI agent to check if source file correctly imports from target file"""
        try:
            client = get_client()
            
            prompt = f"""You are analyzing code coupling between two files.

Source File: {os.path.relpath(source_file, self.project_root)}
Target File: {os.path.relpath(target_file, self.project_root)}
Dependency: {dependency}

Source File Content:
```
{source_content[:2000]}
```

Target File Content:
```
{target_content[:2000]}
```

Analyze if the source file correctly imports and uses the target file. Check:
1. Are the imports/exports matching?
2. Are the symbols being imported actually exported/available in the target file?
3. Is there any mismatch in function signatures, class names, or module structure?

Respond with JSON:
{{"has_error": true/false, "error_type": "TYPE", "message": "description"}}

If no error, set has_error to false."""
            
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt
            )
            
            text = response.text or ""
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if result.get("has_error"):
                    return DependencyError(
                        file_path=source_file,
                        error_type=result.get("error_type", "COUPLING_MISMATCH"),
                        message=result.get("message", "Coupling mismatch detected"),
                        dependency=dependency,
                        affected_files=[target_file]
                    )
            return None
        except Exception as e:
            print(f"⚠️  AI coupling check failed: {e}")
            return None
    
    def run_feedback_loop(self) -> Dict[str, any]:
        """Run the dependency feedback loop"""
        print("=" * 80)
        print("🔄 Starting Dependency Feedback Loop")
        print("=" * 80)
        
        all_files = self.walk_project_files()
        previous_errors = set()
        stuck_iterations = 0
        max_stuck_iterations = 3
        
        for iteration in range(1, self.max_iterations + 1):
            print(f"\n📊 Iteration {iteration}/{self.max_iterations}")
            print("-" * 80)
            print(f"📋 Starting dependency analysis for {len(all_files)} files")
            
            all_errors = []
            
            for file_path in all_files:
                errors = self.check_file_dependencies(file_path, fix_immediately=False)
                all_errors.extend(errors)
            
            if not all_errors:
                print("\n✅ All dependencies resolved!")
                return {
                    "success": True,
                    "iterations": iteration,
                    "remaining_errors": []
                }
            
            current_error_signatures = {
                (e.file_path, e.error_type, e.message[:100]) for e in all_errors
            }
            
            if current_error_signatures == previous_errors:
                stuck_iterations += 1
                print(f"\n⚠️  Errors unchanged for {stuck_iterations} iteration(s)")
                
                if stuck_iterations >= max_stuck_iterations:
                    print(f"\n🛑 Stopping: Same errors detected for {max_stuck_iterations} consecutive iterations")
                    print("   Errors may be unresolvable (e.g., missing files, circular dependencies)")
                    return {
                        "success": False,
                        "iterations": iteration,
                        "remaining_errors": [e.to_dict() for e in all_errors],
                        "reason": "stuck_errors"
                    }
            else:
                stuck_iterations = 0
                previous_errors = current_error_signatures
            
            fixable_errors = []
            unfixable_errors = []
            
            for error in all_errors:
                if error.error_type == "FILE_NOT_FOUND":
                    if not os.path.exists(error.file_path):
                        has_existing_files = any(
                            os.path.exists(af) for af in error.affected_files if af
                        )
                        if not has_existing_files:
                            unfixable_errors.append(error)
                            print(f"⚠️  Skipping unfixable error: {error.error_type} - {error.message[:60]}...")
                            continue
                fixable_errors.append(error)
            
            if unfixable_errors:
                print(f"\n⚠️  {len(unfixable_errors)} unfixable errors (missing files) - skipping")
            
            if not fixable_errors:
                print("\n⚠️  All remaining errors are unfixable (missing files)")
                return {
                    "success": False,
                    "iterations": iteration,
                    "remaining_errors": [e.to_dict() for e in all_errors],
                    "reason": "unfixable_errors"
                }
            
            print(f"\n⚠️  Found {len(all_errors)} errors after iteration {iteration} ({len(fixable_errors)} fixable, {len(unfixable_errors)} unfixable)")
            
            if fixable_errors:
                fix_plan = self._plan_error_fixes(fixable_errors)
                if fix_plan:
                    print(f"\n🔧 Applying {len(fix_plan)} fixes...")
                    fixes_applied = 0
                    for error_info in fix_plan:
                        if self._fix_error(error_info):
                            fixes_applied += 1
                    print(f"✅ Applied {fixes_applied}/{len(fix_plan)} fixes")
        
        print("\n⚠️  Maximum iterations reached. Some errors remain.")
        return {
            "success": False,
            "iterations": self.max_iterations,
            "remaining_errors": [e.to_dict() for e in all_errors],
            "reason": "max_iterations"
        }
    
    def _plan_error_fixes(self, errors: List[DependencyError]) -> List[Dict[str, str]]:
        """Use common planning agent to create prioritized fix plan"""
        try:
            project_structure_tree = self._build_project_structure_tree()
            
            errors_list = []
            for e in errors:
                errors_list.append({
                    "error": e.message,
                    "file": os.path.relpath(e.file_path, self.project_root) if e.file_path else "",
                    "line_number": None,
                    "error_type": e.error_type
                })
            
            prompt = self.pm.render("common_error_planning.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_structure_tree=project_structure_tree,
                project_root=self.project_root,
                errors=errors_list,
                error_type="dependency",
                logs=""
            )
            
            client = get_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt
            )
            
            response_text = response.text.strip()
            
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                fix_plan = json.loads(json_match.group())
            else:
                fix_plan = json.loads(response_text)
            
            if isinstance(fix_plan, dict):
                fix_plan = [fix_plan]
            
            fix_plan = sorted(fix_plan, key=lambda x: x.get('priority', 999))
            return fix_plan
            
        except Exception as e:
            print(f"⚠️  Error in planning agent: {e}")
            return [{"error": e.message, "solution": "Fix dependency error", "filepath": os.path.relpath(e.file_path, self.project_root) if e.file_path else "", "priority": 1} for e in errors]
    
    def _fix_error(self, error_info: Dict[str, str]) -> bool:
        """Fix a single error using common error correcting agent"""
        filepath = error_info.get("filepath", "")
        error = error_info.get("error", "")
        solution = error_info.get("solution", "")
        
        if filepath and not os.path.isabs(filepath):
            file_path = os.path.join(self.project_root, filepath)
        else:
            file_path = filepath
        
        if not file_path or not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path} - Cannot fix error")
            return False
        
        print(f"🔧 Fixing error in {os.path.relpath(file_path, self.project_root)}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            project_structure_tree = self._build_project_structure_tree()
            file_rel_path = os.path.relpath(file_path, self.project_root)
            
            prompt = self.pm.render("common_error_correction.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_structure_tree=project_structure_tree,
                project_root=self.project_root,
                file_rel_path=file_rel_path,
                error=error,
                solution=solution,
                file_content=file_content
            )
            
            client = get_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt
            )
            
            fixed_content = response.text.strip()
            
            if fixed_content.startswith('```'):
                lines = fixed_content.split('\n')
                if len(lines) > 1:
                    fixed_content = '\n'.join(lines[1:])
                    if fixed_content.endswith('```'):
                        fixed_content = fixed_content[:-3].rstrip()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            print(f"✅ Fixed {os.path.relpath(file_path, self.project_root)}")
            return True
            
        except Exception as e:
            print(f"❌ Error fixing file {file_path}: {e}")
            return False


def resolve_dependencies(project_root: str, dependency_analyzer: DependencyAnalyzer,
                        software_blueprint: Optional[Dict] = None,
                        folder_structure: Optional[str] = None,
                        file_output_format: Optional[Dict] = None,
                        pm: Optional[PromptManager] = None) -> Dict[str, any]:
    """
    Main function to resolve dependencies in a project
    
    Args:
        project_root: Root directory of the project
        dependency_analyzer: DependencyAnalyzer instance with project files loaded
        software_blueprint: Software blueprint dictionary
        folder_structure: Folder structure string
        file_output_format: File output format dictionary
        pm: Optional PromptManager instance
    
    Returns:
        Dictionary with resolution results
    """
    feedback_loop = DependencyFeedbackLoop(
        dependency_analyzer, 
        project_root, 
        software_blueprint=software_blueprint,
        folder_structure=folder_structure,
        file_output_format=file_output_format,
        pm=pm
    )
    return feedback_loop.run_feedback_loop()


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dependency_resolver.py <project_root>")
        sys.exit(1)
    
    project_root = sys.argv[1]
    
    if not os.path.exists(project_root):
        print(f"Error: Project root '{project_root}' does not exist")
        sys.exit(1)
    
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
    
    result = resolve_dependencies(project_root, analyzer)
    
    print("\n" + "=" * 80)
    print("📊 Final Results:")
    print(json.dumps(result, indent=2))
    print("=" * 80)
