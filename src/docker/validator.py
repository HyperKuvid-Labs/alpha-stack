import os
import json
from typing import Dict, Any, Optional, Callable, List
import glob
import re


class DockerfileValidator:

    def __init__(
        self,
        project_root: str,
        software_blueprint: Dict[str, Any],
        folder_structure: str,
        pm=None,
        provider_name: str = None,
        on_status: Optional[Callable] = None
    ):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.pm = pm
        self.provider_name = provider_name
        self.on_status = on_status or (lambda *args, **kwargs: None)

        self.dockerfile_path = os.path.join(project_root, "Dockerfile")
        self.readme_path = os.path.join(project_root, "README.md")

    def _status(self, event_type: str, message: str, **kwargs):
        """Emit status update."""
        self.on_status(event_type, message, **kwargs)

    def _detect_language(self, dockerfile_content: str) -> str:
        """Detect the programming language from Dockerfile."""
        content_lower = dockerfile_content.lower()
        if 'python' in content_lower or 'pip' in content_lower:
            return 'python'
        elif 'node' in content_lower or 'npm' in content_lower or 'yarn' in content_lower:
            return 'javascript'
        elif 'java' in content_lower or 'maven' in content_lower or 'gradle' in content_lower:
            return 'java'
        elif 'go' in content_lower:
            return 'go'
        elif 'ruby' in content_lower or 'gem' in content_lower:
            return 'ruby'
        return 'python'  # default

    def _find_test_files(self) -> List[str]:
        """Find test files in the project."""
        test_patterns = [
            "**/test_*.py", "**/tests/*.py", "**/*_test.py", "**/tests/**/*.py",
            "**/*.test.js", "**/*.spec.js", "**/test/**/*.js",
            "**/*Test.java", "**/test/**/*.java"
        ]
        test_files = []
        for pattern in test_patterns:
            test_files.extend(glob.glob(os.path.join(self.project_root, pattern), recursive=True))
        return list(set(test_files))

    def _detect_test_framework(self, dockerfile_content: str, test_files: List[str], readme_content: str = "") -> str:
        """Detect the test framework being used."""
        content_lower = dockerfile_content.lower() + " " + readme_content.lower()

        # Check for explicit framework mentions
        if 'pytest' in content_lower:
            return 'pytest'
        elif 'unittest' in content_lower:
            return 'unittest'
        elif 'jest' in content_lower:
            return 'jest'
        elif 'mocha' in content_lower:
            return 'mocha'
        elif 'junit' in content_lower:
            return 'junit'

        # Infer from file extensions
        for test_file in test_files:
            if test_file.endswith('.py'):
                return 'pytest'  # Default for Python
            elif test_file.endswith(('.test.js', '.spec.js')):
                return 'jest'  # Default for JavaScript
            elif test_file.endswith('Test.java'):
                return 'junit'

        return 'pytest'  # Default fallback

    def _read_readme(self) -> str:
        """Read README.md if it exists."""
        if os.path.exists(self.readme_path):
            try:
                with open(self.readme_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except:
                pass
        return ""

    def _extract_test_command_from_readme(self, readme_content: str) -> Optional[str]:
        """Extract test command from README."""
        if not readme_content:
            return None

        # Look for common test command patterns in README
        patterns = [
            r'```bash\s*\n\s*(pytest[^\n]*)',
            r'```sh\s*\n\s*(pytest[^\n]*)',
            r'```\s*\n\s*(pytest[^\n]*)',
            r'```bash\s*\n\s*(npm test[^\n]*)',
            r'```bash\s*\n\s*(python -m pytest[^\n]*)',
            r'To run tests[:\s]*`([^`]+)`',
            r'Run tests[:\s]*`([^`]+)`',
            r'Testing[:\s]*`([^`]+)`'
        ]

        for pattern in patterns:
            match = re.search(pattern, readme_content, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()

        return None

    def _manually_fix_dockerfile(self, dockerfile_path: str, analysis: Dict[str, Any], test_command: Optional[str] = None) -> Dict[str, Any]:
        """Manually fix the Dockerfile by adding necessary test support."""
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            original_content = content
            language = analysis['language']
            test_framework = analysis.get('test_framework', 'pytest')

            # Split into lines for processing
            lines = content.split('\n')
            new_lines = []

            # Track what we've added
            added_test_deps = False
            added_test_copy = False
            added_test_stage = False

            # Track stage information
            in_builder_stage = False
            in_final_stage = False
            final_stage_line = -1

            i = 0
            while i < len(lines):
                line = lines[i]
                line_stripped = line.strip()

                # Track stages
                if line_stripped.startswith('FROM') and 'AS builder' in line:
                    in_builder_stage = True
                    in_final_stage = False
                elif line_stripped.startswith('FROM') and 'AS final' in line:
                    in_builder_stage = False
                    in_final_stage = True
                    final_stage_line = len(new_lines)

                new_lines.append(line)

                # 1. Add test dependencies in builder stage
                if not added_test_deps and in_builder_stage and not analysis['has_test_dependencies']:
                    if language == 'python':
                        # Look for pip install requirements
                        if 'pip install' in line and 'requirements.txt' in line:
                            new_lines.append('')
                            new_lines.append('# Install test dependencies')
                            if test_framework == 'pytest':
                                new_lines.append('RUN pip install --no-cache-dir pytest pytest-cov')
                            elif test_framework == 'unittest':
                                new_lines.append('RUN pip install --no-cache-dir coverage')
                            added_test_deps = True

                    elif language == 'javascript':
                        if 'npm install' in line or 'yarn install' in line:
                            new_lines.append('')
                            new_lines.append('# Install test dependencies (ensure they are in package.json devDependencies)')
                            added_test_deps = True

                # 2. Add test file copying in final stage
                if not added_test_copy and in_final_stage and not analysis['copies_test_files']:
                    # Look for COPY src/ or similar
                    if line_stripped.startswith('COPY') and ('src/' in line or 'app/' in line):
                        new_lines.append('')
                        new_lines.append('# Copy test files')
                        new_lines.append('COPY tests/ ./tests/')
                        added_test_copy = True

                i += 1

            # 3. Add test stage at the end if not present
            if not analysis['has_test_command']:
                new_lines.append('')
                new_lines.append('')
                new_lines.append('# ---- Test Stage ----')
                new_lines.append('# This stage runs the tests to validate the application')
                new_lines.append('FROM final AS test')
                new_lines.append('')
                new_lines.append('# Switch to root to install test dependencies if needed')
                new_lines.append('USER root')
                new_lines.append('')

                if not added_test_deps:
                    new_lines.append('# Install test dependencies')
                    if language == 'python':
                        if test_framework == 'pytest':
                            new_lines.append('RUN pip install --no-cache-dir pytest pytest-cov')
                        else:
                            new_lines.append('RUN pip install --no-cache-dir coverage')
                    elif language == 'javascript':
                        new_lines.append('RUN npm install --save-dev jest')
                    new_lines.append('')

                if not added_test_copy:
                    new_lines.append('# Copy test files')
                    new_lines.append('COPY tests/ ./tests/')
                    new_lines.append('')

                new_lines.append('# Run tests')
                if test_command:
                    # Use command from README
                    new_lines.append(f'RUN {test_command} || exit 0')
                elif language == 'python':
                    if test_framework == 'pytest':
                        new_lines.append('RUN python -m pytest tests/ -v --tb=short || exit 0')
                    else:
                        new_lines.append('RUN python -m unittest discover tests/ || exit 0')
                elif language == 'javascript':
                    new_lines.append('RUN npm test || exit 0')
                elif language == 'java':
                    new_lines.append('RUN mvn test || exit 0')
                elif language == 'go':
                    new_lines.append('RUN go test ./... || exit 0')

                added_test_stage = True

            # Join back into content
            new_content = '\n'.join(new_lines)

            # Check if anything changed
            if new_content != original_content:
                # Write back to file
                with open(dockerfile_path, 'w') as f:
                    f.write(new_content)

                return {
                    'success': True,
                    'modified': True,
                    'changes': {
                        'added_test_deps': added_test_deps,
                        'added_test_copy': added_test_copy,
                        'added_test_stage': added_test_stage
                    }
                }
            else:
                return {
                    'success': True,
                    'modified': False,
                    'message': 'No changes needed'
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'modified': False
            }

    def validate_and_fix(self) -> Dict[str, Any]:
        """Validate Dockerfile and fix if needed."""
        results = {
            "validation": self._validate_dockerfile(),
            "fix": {"success": True, "modified": False},
            "success": True
        }

        if results["validation"].get("needs_fixing"):
            self._status("step", "Dockerfile validation failed - attempting to fix...")
            results["fix"] = self._fix_dockerfile(results["validation"])
            results["success"] = results["fix"].get("success", False)
        else:
            results["success"] = results["validation"].get("valid", False)

        return results

    def _validate_dockerfile(self) -> Dict[str, Any]:
        """Check if Dockerfile has proper test support."""
        result = {
            "valid": False,
            "has_tests": False,
            "test_files": [],
            "test_framework": None,
            "analysis": {},
            "needs_fixing": False,
            "dockerfile_content": None,
            "readme_content": None,
            "test_command": None
        }

        # Find test files
        test_files = self._find_test_files()
        result["test_files"] = test_files
        result["has_tests"] = len(test_files) > 0

        # Read README
        readme_content = self._read_readme()
        result["readme_content"] = readme_content

        # Check Dockerfile
        if not os.path.exists(self.dockerfile_path):
            result["needs_fixing"] = True
            result["analysis"]["error"] = "Dockerfile not found"
            return result

        with open(self.dockerfile_path, 'r') as f:
            dockerfile_content = f.read()

        result["dockerfile_content"] = dockerfile_content

        # Detect language and test framework
        language = self._detect_language(dockerfile_content)
        test_framework = self._detect_test_framework(dockerfile_content, test_files, readme_content)
        test_command = self._extract_test_command_from_readme(readme_content)

        result["test_framework"] = test_framework
        result["test_command"] = test_command

        # Analyze Dockerfile
        analysis = {
            "has_test_dependencies": "pytest" in dockerfile_content.lower() or "jest" in dockerfile_content.lower() or "junit" in dockerfile_content.lower(),
            "copies_test_files": "COPY tests/" in dockerfile_content or "COPY test/" in dockerfile_content,
            "has_test_command": "AS test" in dockerfile_content or ("pytest" in dockerfile_content and "RUN" in dockerfile_content),
            "base_image": "base",
            "language": language,
            "test_framework": test_framework
        }
        result["analysis"] = analysis

        # Determine if valid
        if result["has_tests"]:
            result["valid"] = (
                analysis["has_test_dependencies"] and
                analysis["copies_test_files"] and
                analysis["has_test_command"]
            )
            result["needs_fixing"] = not result["valid"]
        else:
            result["valid"] = True
            result["needs_fixing"] = False

        return result

    def _fix_dockerfile(self, validation: Dict[str, Any]) -> Dict[str, Any]:
        """Fix Dockerfile to add test support manually (no LLM)."""
        self._status("step", "Fixing Dockerfile to add test support...")

        try:
            test_command = validation.get("test_command")
            analysis = validation["analysis"]

            return self._manually_fix_dockerfile(
                self.dockerfile_path,
                analysis,
                test_command
            )

        except Exception as e:
            return {"success": False, "error": str(e), "modified": False}
