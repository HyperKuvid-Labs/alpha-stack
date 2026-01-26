import os
from typing import List, Optional, Dict, Set
from .helpers import clean_agent_output, MODEL_NAME
from .prompt_manager import PromptManager
from .inference import InferenceManager


DEPENDENCY_FILENAMES = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "Pipfile",
    "Pipfile.lock",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "gradle.properties",
    "CMakeLists.txt",
}


def extract_all_external_dependencies(dependency_analyzer, project_root: str) -> List[str]:
    """Extract all external dependencies from all files in the project."""
    external_deps = set()
    
    # Get all project files
    for file_path in dependency_analyzer.project_files:
        if not os.path.exists(file_path):
            continue
        
        # Get dependency details for this file
        dep_details = dependency_analyzer.get_dependency_details(file_path)
        
        # Extract external dependencies
        for dep in dep_details:
            if isinstance(dep, dict) and dep.get("kind") == "external":
                raw_dep = dep.get("raw", "").strip()
                if raw_dep:
                    external_deps.add(raw_dep)
    
    # Return sorted list
    return sorted(list(external_deps))


class DependencyFileGenerator:
    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict,
                 external_dependencies: List[str],
                 pm: Optional[PromptManager] = None,
                 model_name: Optional[str] = None,
                 provider_name: Optional[str] = None,
                 on_status=None):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.external_dependencies = external_dependencies
        self.pm = pm or PromptManager()
        self.model_name = model_name or MODEL_NAME
        self.provider_name = provider_name
        self.on_status = on_status
    
    def _emit(self, event_type: str, message: str, **kwargs):
        if self.on_status:
            self.on_status(event_type, message, **kwargs)
    
    def generate_all(self) -> Dict:
        results = {
            "generated_files": [],
            "success": True
        }
        if self.provider_name is None:
            if self.model_name.startswith("models/"):
                provider_name = "google"
            else:
                provider_name = "openrouter"
        else:
            provider_name = self.provider_name
        
        provider = InferenceManager.create_provider(provider_name)
        
        # Create prompt for dependency file generation
        prompt = self.pm.render(
            "dependency_file_generation.j2",
            project_root=self.project_root,
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            external_dependencies=self.external_dependencies
        )
        
        messages = [{"role": "user", "content": prompt}]
        response = provider.call_model(messages, model=self.model_name)
        content = provider.extract_text(response)
        
        content = clean_agent_output(content)
        generated_files = self._save_dependency_files(content)
        
        results["generated_files"] = generated_files
        return results
    
    def _save_dependency_files(self, content: str) -> List[str]:
        generated_files = []
        parts = content.split("===")
        allowed_files = self._get_allowed_dependency_files()
        
        i = 0
        while i < len(parts):
            part = parts[i].strip()
            if not part:
                i += 1
                continue
            if i + 1 < len(parts):
                filename = os.path.basename(part.strip())
                file_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
                
                # Only write known dependency files that exist in folder structure
                if filename and file_content and filename in allowed_files:
                    # Save the file
                    file_path = os.path.join(self.project_root, filename)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(file_content)
                    generated_files.append(filename)
                    self._emit("step", f"Generated dependency file: {filename}")
                    i += 2
                    continue
            
            i += 1
        if not generated_files and content.strip():
            # If there is exactly one allowed dependency file, write content to it.
            if len(allowed_files) == 1:
                filename = next(iter(allowed_files))
                file_path = os.path.join(self.project_root, filename)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content.strip())
                generated_files.append(filename)
                self._emit("step", f"Generated dependency file: {filename}")
        
        return generated_files

    def _get_allowed_dependency_files(self) -> Set[str]:
        """Get dependency files that exist in the folder structure."""
        filenames = set()
        for line in self.folder_structure.splitlines():
            name = self._extract_name_from_tree_line(line)
            if name:
                filenames.add(name)
        # Only allow known dependency files
        return {name for name in filenames if name in DEPENDENCY_FILENAMES}

    @staticmethod
    def _extract_name_from_tree_line(line: str) -> Optional[str]:
        if not line or not line.strip():
            return None
        cleaned = line.strip()
        cleaned = cleaned.replace("├── ", "").replace("└── ", "").replace("│   ", "")
        cleaned = cleaned.split("#")[0].strip()
        if cleaned.endswith("/"):
            return None
        # Avoid weird separators
        cleaned = cleaned.split("  ")[0].strip()
        if not cleaned:
            return None
        return cleaned
