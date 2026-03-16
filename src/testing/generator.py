import os
from typing import Dict, Optional
from ..utils.helpers import clean_agent_output
from ..utils.prompt_manager import PromptManager
from ..utils.error_tracker import ErrorTracker


def generate_dockerignore_content() -> str:
    return """# Git
.git
.gitignore
.gitattributes

# IDE and editors
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.env
.venv
env/
venv/
ENV/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
eggs/
.eggs/

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm
.yarn

# Rust
target/
Cargo.lock

# Go
vendor/

# Build artifacts
*.log
*.tmp
*.temp
coverage/
.coverage
htmlcov/

# Documentation (not needed in container)
docs/
*.md
!README.md

# Tests (run separately via docker run)
*.test.*
*.spec.*
pytest.ini
jest.config.*
.pytest_cache/

# Docker files (avoid recursive copying)
Dockerfile*
docker-compose*
.docker/

# CI/CD
.github/
.gitlab-ci.yml
.travis.yml
Jenkinsfile
.circleci/

# Misc
*.bak
*.orig
.env.local
.env.*.local
"""


class TestFileGenerator:
    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict,
                 metadata_dict: Dict, dependency_analyzer,
                 pm: Optional[PromptManager] = None, on_status=None,
                 provider=None):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm or PromptManager(templates_dir="prompts")
        self.error_tracker = ErrorTracker(project_root)
        self.on_status = on_status
        self.provider = provider

    def _emit(self, event_type: str, message: str, **kwargs):
        if self.on_status:
            self.on_status(event_type, message, **kwargs)

    def generate_dockerfile(self) -> bool:
        try:
            prompt = self.pm.render("dockerfile_generation.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                file_summaries={},
                external_dependencies=[],
                project_root=self.project_root
            )

            messages = [{"role": "user", "content": prompt}]
            response = self.provider.call_model(messages)
            dockerfile_content = clean_agent_output(self.provider.extract_text(response))

            dockerfile_path = os.path.join(self.project_root, "Dockerfile")
            with open(dockerfile_path, 'w', encoding='utf-8') as f:
                f.write(dockerfile_content)

            dockerignore_path = os.path.join(self.project_root, ".dockerignore")
            with open(dockerignore_path, 'w', encoding='utf-8') as f:
                f.write(generate_dockerignore_content())

            self.error_tracker.log_change(
                file_path=dockerfile_path,
                change_description="Generated Dockerfile and .dockerignore from project metadata",
                error_context="Dockerfile generation phase",
                actions=["generate_dockerfile", "generate_dockerignore"]
            )

            return True

        except Exception as e:
            self._emit("error", f"Dockerfile generation failed: {e}")
            return False
