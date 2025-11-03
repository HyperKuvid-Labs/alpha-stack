import os
import json
import re
import subprocess
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from genai_client import get_client
from prompt_manager import PromptManager


class DockerBuildError:
    """Represents a Docker build error"""
    def __init__(self, error_message: str, file: Optional[str] = None, 
                 line_number: Optional[int] = None, error_type: Optional[str] = None):
        self.error_message = error_message
        self.file = file
        self.line_number = line_number
        self.error_type = error_type or "BUILD_ERROR"
    
    def to_dict(self):
        return {
            "error": self.error_message,
            "file": self.file or "",
            "line_number": self.line_number,
            "error_type": self.error_type
        }
    
    def __repr__(self):
        return f"DockerBuildError(file={self.file}, error={self.error_message[:50]}...)"
    
    def __str__(self):
        return json.dumps(self.to_dict())


class DockerTestingPipeline:
    """Handles Docker testing and CI/CD pipeline"""
    
    def __init__(self, project_root: str, software_blueprint: Dict, 
                 folder_structure: str, file_output_format: Dict, pm: Optional[PromptManager] = None):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm or PromptManager(templates_dir="prompts")
        self.max_iterations = 50
        self.dockerfile_path = os.path.join(project_root, "Dockerfile")
        
    def generate_dockerfile(self) -> bool:
        """Generate Dockerfile for the project"""
        try:
            print("🐳 Generating Dockerfile...")
            
            client = get_client()
            prompt = self.pm.render("dockerfile_generation.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_root=self.project_root
            )
            
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt
            )
            
            dockerfile_content = response.text.strip()
            
            if dockerfile_content.startswith('```'):
                lines = dockerfile_content.split('\n')
                if len(lines) > 1:
                    dockerfile_content = '\n'.join(lines[1:])
                    if dockerfile_content.endswith('```'):
                        dockerfile_content = dockerfile_content[:-3].rstrip()
            
            with open(self.dockerfile_path, 'w') as f:
                f.write(dockerfile_content)
            
            print(f"Dockerfile generated at {self.dockerfile_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error generating Dockerfile: {e}")
            return False
    
    def build_docker_image(self) -> Tuple[bool, str]:
        """Build Docker image and return logs"""
        print("🔨 Building Docker image...")
        
        try:
            result = subprocess.run(
                ['docker', 'build', '-t', 'project-test', '.'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            combined_output = result.stdout + "\n" + result.stderr
            
            if result.returncode == 0:
                print("✅ Docker build successful!")
                return True, combined_output
            else:
                print(f"❌ Docker build failed")
                return False, combined_output
                
        except subprocess.TimeoutExpired:
            return False, "Docker build timeout (exceeded 10 minutes)"
        except Exception as e:
            return False, f"Docker build error: {str(e)}"
    
    def plan_error_fixes(self, logs: str, error_type: str = "build") -> List[Dict[str, str]]:
        """Use planning agent to parse logs, classify errors, and create prioritized fix plan"""
        error_type_label = error_type.upper().replace("_", " ")
        print(f"📋 Planning {error_type_label} error fixes from logs...")
        
        try:
            project_structure_tree = self._build_project_structure_tree()
            
            prompt = self.pm.render("common_error_planning.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_structure_tree=project_structure_tree,
                project_root=self.project_root,
                error_type=error_type,
                logs=logs[-5000:] if logs else "",  # Pass full logs, let agent parse
                errors=[]  # Empty - agent will parse from logs
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
            
            print(f"✅ Generated fix plan with {len(fix_plan)} prioritized fixes")
            return fix_plan
            
        except Exception as e:
            print(f"⚠️  Error in planning agent: {e}")
            return []
    
    def fix_error(self, error_info: Dict[str, str]) -> bool:
        """Fix a single error using common error correcting agent"""
        filepath = error_info.get("filepath", error_info.get("file", ""))
        error = error_info.get("error", "")
        solution = error_info.get("solution", "")
        
        if filepath and not os.path.isabs(filepath):
            file_path = os.path.join(self.project_root, filepath)
        else:
            file_path = filepath
        
        if not file_path or not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path} - Cannot fix error in non-existent file")
            print(f"   Error: {error[:100]}...")
            print(f"   💡 This error will be skipped. Consider creating the file first or fixing the reference.")
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
    
    
    def run_project_in_docker(self) -> Tuple[bool, str]:
        """
        Run the project in STRONGLY SANDBOXED Docker container
        
        Security features:
        - No network access (--network none)
        - Read-only filesystem (--read-only)
        - Non-root user (--user 1000:1000)
        - Dropped capabilities (--cap-drop ALL)
        - Resource limits (memory, CPU, processes)
        - Timeout protection (5 minutes)
        """
        print(" Running project in SECURE SANDBOXED environment...")
        print("   Isolation: Network disabled, read-only FS, non-root, resource-limited")
        
        try:
            run_command = self._get_run_command()
            
            docker_args = [
                'docker', 'run',
                '--rm',
                '--network', 'none',
                '--read-only',
                '--tmpfs', '/tmp:rw,noexec,nosuid',
                '--tmpfs', '/run:rw,noexec,nosuid',
                '--user', '1000:1000',
                '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges',
                '--memory', '512m',
                '--memory-swap', '512m',
                '--cpus', '1.0',
                '--pids-limit', '100',
                '--ulimit', 'nofile=1024:1024',
                '--ulimit', 'nproc=100:100',
                '--log-driver', 'none',
                'project-test'
            ] + run_command
            
            print(f"   Command: {' '.join(run_command)}")
            
            result = subprocess.run(
                docker_args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            full_logs = result.stdout + "\n" + result.stderr
            
            if result.returncode == 0:
                print("✅ Project ran successfully in sandbox!")
                return True, full_logs
            else:
                print(f"❌ Project failed")
                return False, full_logs
                
        except subprocess.TimeoutExpired:
            print("⏱️  Sandbox timeout - container killed after 1 minute")
            return False, "Sandbox timeout (1 minute)"
        except Exception as e:
            print(f"❌ Sandbox execution error: {e}")
            return False, f"Sandbox error: {str(e)}"
    
    def run_tests_in_docker(self) -> Tuple[bool, str]:
        """
        Run CI/CD tests in sandboxed Docker container
        """
        print("🧪 Running CI/CD tests in sandboxed environment...")
        
        try:
            # Use AI agent to detect test command
            test_command = self._get_test_command()
            
            docker_args = [
                'docker', 'run',
                '--rm',
                '--network', 'none',
                '--read-only',
                '--tmpfs', '/tmp:rw,noexec,nosuid',
                '--tmpfs', '/run:rw,noexec,nosuid',
                '--tmpfs', '/app/.pytest_cache:rw',
                '--user', '1000:1000',
                '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges',
                '--memory', '512m',
                '--memory-swap', '512m',
                '--cpus', '1.0',
                '--pids-limit', '100',
                '--log-driver', 'none',
                'project-test'
            ] + test_command
            
            print(f"   Test command: {' '.join(test_command)}")
            
            result = subprocess.run(
                docker_args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            full_logs = result.stdout + "\n" + result.stderr
            
            if result.returncode == 0:
                print("✅ All tests passed!")
                return True, full_logs
            else:
                print(f"❌ Tests failed")
                return False, full_logs
                
        except subprocess.TimeoutExpired:
            print("⏱️  Test timeout - container killed after 2 minutes")
            return False, "Test timeout (2 minutes)"
        except Exception as e:
            print(f"❌ Test execution error: {e}")
            return False, f"Test error: {str(e)}"
    
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
    
    def _get_project_context(self) -> Dict[str, str]:
        """Get context from key project files"""
        context = {}
        
        key_files = ['requirements.txt', 'package.json', 'pom.xml', 'Cargo.toml', 
                     'go.mod', 'setup.py', 'pyproject.toml']
        
        for filename in key_files:
            file_path = os.path.join(self.project_root, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        context[filename] = f.read()[:2000]
                except:
                    pass
        
        if os.path.exists(self.dockerfile_path):
            try:
                with open(self.dockerfile_path, 'r', encoding='utf-8') as f:
                    context['Dockerfile'] = f.read()
            except:
                pass
        
        return context
    
    def _detect_entry_point_with_agent(self) -> List[str]:
        """Use AI agent to detect entry point"""
        try:
            print("🔍 Detecting entry point using AI agent...")
            
            project_structure_tree = self._build_project_structure_tree()
            
            python_files = []
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for file in files:
                    if file.endswith('.py'):
                        rel_path = os.path.relpath(os.path.join(root, file), self.project_root)
                        python_files.append(rel_path)
            
            prompt = self.pm.render("entry_point_detection.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_structure_tree=project_structure_tree,
                python_files=python_files,
                project_root=self.project_root
            )
            
            client = get_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt
            )
            
            response_text = response.text.strip()
            
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    command = result.get("command", [])
                    
                    if command and isinstance(command, list):
                        command = [str(arg) for arg in command if arg]
                        if command:
                            print(f"✅ Entry point detected: {' '.join(command)}")
                            return command
                    elif command and isinstance(command, str):
                        print(f"⚠️  Command is string, converting to list: {command}")
                        command_list = command.split()
                        if command_list:
                            print(f"✅ Entry point detected: {' '.join(command_list)}")
                            return command_list
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error: {e}")
                    print(f"   Raw response: {response_text[:200]}")
            
            print("⚠️  Failed to detect entry point with AI, using fallback")
            return ["python", "main.py"]
        except Exception as e:
            print(f"⚠️  Error in entry point detection: {e}")
            return ["python", "main.py"]
    
    def _get_run_command(self) -> List[str]:
        """Determine how to run the project using AI agent"""
        return self._detect_entry_point_with_agent()
    
    def _detect_test_command_with_agent(self) -> List[str]:
        """Use AI agent to detect test command"""
        try:
            print("🔍 Detecting test command using AI agent...")
            
            project_structure_tree = self._build_project_structure_tree()
            
            # Find test files
            test_files = []
            test_dirs = ['tests', 'test', '__tests__']
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for file in files:
                    if file.startswith('test_') or file.endswith('_test.py') or file.endswith('_test.js') or file.endswith('_test.ts'):
                        rel_path = os.path.relpath(os.path.join(root, file), self.project_root)
                        test_files.append(rel_path)
                
                # Check if this directory is a test directory
                dir_name = os.path.basename(root)
                if dir_name in test_dirs:
                    for file in files:
                        if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')) and not file.startswith('.'):
                            rel_path = os.path.relpath(os.path.join(root, file), self.project_root)
                            if rel_path not in test_files:
                                test_files.append(rel_path)
            
            # Find config files
            config_files = []
            config_patterns = [
                'pytest.ini', 'pyproject.toml', 'setup.cfg', 'jest.config.js', 'jest.config.ts',
                'jest.config.json', 'mocha.opts', 'package.json', 'pom.xml', 'build.gradle',
                'Cargo.toml', 'go.mod', 'Gemfile'
            ]
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for file in files:
                    if file in config_patterns:
                        rel_path = os.path.relpath(os.path.join(root, file), self.project_root)
                        config_files.append(rel_path)
            
            prompt = self.pm.render("test_command_detection.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                project_structure_tree=project_structure_tree,
                test_files=test_files[:50],  # Limit to avoid token limits
                config_files=config_files[:20],  # Limit to avoid token limits
                project_root=self.project_root
            )
            
            client = get_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt
            )
            
            response_text = response.text.strip()
            
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    command = result.get("command", [])
                    
                    if command and isinstance(command, list):
                        command = [str(arg) for arg in command if arg]
                        if command:
                            print(f"✅ Test command detected: {' '.join(command)}")
                            return command
                    elif command and isinstance(command, str):
                        print(f"⚠️  Command is string, converting to list: {command}")
                        command_list = command.split()
                        if command_list:
                            print(f"✅ Test command detected: {' '.join(command_list)}")
                            return command_list
                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error: {e}")
                    print(f"   Raw response: {response_text[:200]}")
            
            print("⚠️  Failed to detect test command with AI, using fallback")
            return ["pytest", "-v"]
        except Exception as e:
            print(f"⚠️  Error in test command detection: {e}")
            return ["pytest", "-v"]
    
    def _get_test_command(self) -> List[str]:
        """Determine how to run tests using AI agent"""
        return self._detect_test_command_with_agent()
    
    def run_testing_pipeline(self) -> Dict[str, any]:
        print("docker build")
        results = {
            "build_success": False,
            "runtime_success": False,
            "tests_success": False,
            "build_iterations": 0,
            "runtime_iterations": 0,
            "test_iterations": 0,
            "success": False
        }
        # Remove existing Dockerfile for fresh regeneration
        # (Dockerfile will be overwritten, but removing ensures clean state)
        if os.path.exists(self.dockerfile_path):
            try:
                os.remove(self.dockerfile_path)
                print(f"   ✅ Removed existing Dockerfile for fresh regeneration")
            except Exception as e:
                print(f"   ⚠️  Could not remove Dockerfile: {e}")
        
        if not self.generate_dockerfile():
            return {
                **results,
                "message": "Failed to generate Dockerfile"
            }
        
        print("\n" + "=" * 80)
        print("STEP 1: Docker Build")
        print("=" * 80)
        
        build_iteration = 0
        previous_build_errors = set()  # Track fix plan signatures instead of errors
        stuck_build_iterations = 0
        max_stuck_iterations = 3
        
        while build_iteration < self.max_iterations:
            build_iteration += 1
            print(f"\n📊 Build Iteration {build_iteration}/{self.max_iterations}")
            print("-" * 80)
            
            success, build_logs = self.build_docker_image()
            
            if success:
                print("\n✅ Docker build successful!")
                results["build_success"] = True
                results["build_iterations"] = build_iteration
                break
            
            # Use planning agent to parse logs and create fix plan
            fix_plan = self.plan_error_fixes(build_logs, error_type="build")
            
            if not fix_plan:
                print("⚠️  No fix plan generated from logs")
                print("\n📋 Build Logs:")
                print(build_logs[-500:] if len(build_logs) > 500 else build_logs)
                break
            
            # Check if fix plan is stuck (same errors)
            current_fix_signatures = {
                (f.get("filepath", ""), f.get("error", "")[:100]) for f in fix_plan
            }
            
            if current_fix_signatures == previous_build_errors:
                stuck_build_iterations += 1
                print(f"\n⚠️  Fix plan unchanged for {stuck_build_iterations} iteration(s)")
                
                if stuck_build_iterations >= max_stuck_iterations:
                    print(f"\n🛑 Stopping build: Same fix plan detected for {max_stuck_iterations} consecutive iterations")
                    break
            else:
                stuck_build_iterations = 0
                previous_build_errors = current_fix_signatures
            
            print(f"\n⚠️  Generated fix plan with {len(fix_plan)} fixes")
            
            print(f"\n🔧 Applying {len(fix_plan)} fixes...")
            fixes_applied = 0
            for i, error_info in enumerate(fix_plan, 1):
                print(f"\n[{i}/{len(fix_plan)}] Fixing: {error_info.get('error', '')[:50]}...")
                if self.fix_error(error_info):
                    fixes_applied += 1
            
            if fixes_applied == 0:
                print("⚠️  No fixes were successfully applied")
                break
        
        if not results["build_success"]:
            return {
                **results,
                "message": "Docker build failed after maximum iterations"
            }
        
        # Step 3: Run project in sandbox and fix loop
        print("\n" + "=" * 80)
        print("Project Runtime (Sandboxed)")
        print("=" * 80)
        
        runtime_iteration = 0
        runtime_logs = ""
        previous_runtime_errors = set()  # Track fix plan signatures instead of errors
        stuck_runtime_iterations = 0
        max_stuck_iterations = 3
        
        while runtime_iteration < self.max_iterations:
            runtime_iteration += 1
            print(f"\n📊 Runtime Iteration {runtime_iteration}/{self.max_iterations}")
            print("-" * 80)
            
            success, runtime_logs = self.run_project_in_docker()
            
            if success:
                print("\n✅ Project runs successfully!")
                results["runtime_success"] = True
                results["runtime_iterations"] = runtime_iteration
                break
            
            # Use planning agent to parse logs and create fix plan
            fix_plan = self.plan_error_fixes(runtime_logs, error_type="runtime")
            
            if not fix_plan:
                print("⚠️  No fix plan generated from logs")
                print("\n📋 Runtime Logs:")
                print(runtime_logs[-500:] if len(runtime_logs) > 500 else runtime_logs)
                break
            
            # Check if fix plan is stuck (same errors)
            current_fix_signatures = {
                (f.get("filepath", ""), f.get("error", "")[:100]) for f in fix_plan
            }
            
            if current_fix_signatures == previous_runtime_errors:
                stuck_runtime_iterations += 1
                print(f"\n⚠️  Fix plan unchanged for {stuck_runtime_iterations} iteration(s)")
                
                if stuck_runtime_iterations >= max_stuck_iterations:
                    print(f"\n🛑 Stopping runtime: Same fix plan detected for {max_stuck_iterations} consecutive iterations")
                    break
            else:
                stuck_runtime_iterations = 0
                previous_runtime_errors = current_fix_signatures
            
            print(f"\n⚠️  Generated fix plan with {len(fix_plan)} fixes")
            print("\n📋 Runtime Logs:")
            print(runtime_logs[-500:] if len(runtime_logs) > 500 else runtime_logs)
            
            print(f"\n🔧 Applying {len(fix_plan)} runtime fixes...")
            fixes_applied = 0
            for i, error_info in enumerate(fix_plan, 1):
                print(f"\n[{i}/{len(fix_plan)}] Fixing: {error_info.get('error', '')[:50]}...")
                if self.fix_error(error_info):
                    fixes_applied += 1
            
            if fixes_applied == 0:
                print("⚠️  No fixes were successfully applied")
                break
            
            print("\n🔨 Rebuilding Docker image after runtime fixes...")
            rebuild_success, rebuild_logs = self.build_docker_image()
            if not rebuild_success:
                print(f"⚠️  Rebuild failed")
                break
        
        if not results["runtime_success"]:
            return {
                **results,
                "message": "Project runtime failed after maximum iterations",
                "runtime_logs": runtime_logs[-1000:] if runtime_logs else ""
            }
        
        # Step 4: Run CI/CD tests and fix loop
        print("\n" + "=" * 80)
        print("STEP 3: CI/CD Tests (Sandboxed)")
        print("=" * 80)
        
        test_iteration = 0
        test_logs = ""
        previous_test_errors = set()  # Track fix plan signatures instead of errors
        stuck_test_iterations = 0
        max_stuck_iterations = 3
        
        while test_iteration < self.max_iterations:
            test_iteration += 1
            print(f"\n📊 Test Iteration {test_iteration}/{self.max_iterations}")
            print("-" * 80)
            
            success, test_logs = self.run_tests_in_docker()
            
            if success:
                print("\n✅ All tests passed!")
                results["tests_success"] = True
                results["test_iterations"] = test_iteration
                break
            
            # Use planning agent to parse logs and create fix plan
            fix_plan = self.plan_error_fixes(test_logs, error_type="test")
            
            if not fix_plan:
                print("⚠️  No fix plan generated from logs")
                print("\n📋 Test Logs:")
                print(test_logs[-500:] if len(test_logs) > 500 else test_logs)
                break
            
            # Check if fix plan is stuck (same errors)
            current_fix_signatures = {
                (f.get("filepath", ""), f.get("error", "")[:100]) for f in fix_plan
            }
            
            if current_fix_signatures == previous_test_errors:
                stuck_test_iterations += 1
                print(f"\n⚠️  Fix plan unchanged for {stuck_test_iterations} iteration(s)")
                
                if stuck_test_iterations >= max_stuck_iterations:
                    print(f"\n🛑 Stopping tests: Same fix plan detected for {max_stuck_iterations} consecutive iterations")
                    break
            else:
                stuck_test_iterations = 0
                previous_test_errors = current_fix_signatures
            
            print(f"\n⚠️  Generated fix plan with {len(fix_plan)} fixes")
            print("\n📋 Test Logs:")
            print(test_logs[-500:] if len(test_logs) > 500 else test_logs)
            
            print(f"\n🔧 Applying {len(fix_plan)} test fixes...")
            fixes_applied = 0
            for i, error_info in enumerate(fix_plan, 1):
                print(f"\n[{i}/{len(fix_plan)}] Fixing: {error_info.get('error', '')[:50]}...")
                if self.fix_error(error_info):
                    fixes_applied += 1
            
            if fixes_applied == 0:
                print("⚠️  No fixes were successfully applied")
                break
            
            print("\n🔨 Rebuilding Docker image after test fixes...")
            rebuild_success, rebuild_logs = self.build_docker_image()
            if not rebuild_success:
                print(f"⚠️  Rebuild failed")
                break
        
        # Final results
        results["success"] = results["build_success"] and results["runtime_success"] and results["tests_success"]
        
        if results["success"]:
            results["message"] = "All pipeline steps successful: Build ✅ Runtime ✅ Tests ✅"
        else:
            results["message"] = f"Pipeline incomplete: Build {'✅' if results['build_success'] else '❌'} Runtime {'✅' if results['runtime_success'] else '❌'} Tests {'✅' if results['tests_success'] else '❌'}"
            if test_logs:
                results["test_logs"] = test_logs[-1000:]
        
        return results


def run_docker_testing(project_root: str, software_blueprint: Dict, 
                      folder_structure: str, file_output_format: Dict,
                      pm: Optional[PromptManager] = None) -> Dict[str, any]:
    pipeline = DockerTestingPipeline(
        project_root=project_root,
        software_blueprint=software_blueprint,
        folder_structure=folder_structure,
        file_output_format=file_output_format,
        pm=pm
    )
    return pipeline.run_testing_pipeline()


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python docker_testing.py <project_root>")
        sys.exit(1)
    
    project_root = sys.argv[1]
    
    if not os.path.exists(project_root):
        print(f"Error: Project root '{project_root}' does not exist")
        sys.exit(1)
    
    # Mock data for testing
    software_blueprint = {}
    folder_structure = ""
    file_output_format = {}
    
    result = run_docker_testing(project_root, software_blueprint, folder_structure, file_output_format)
    
    print("\n" + "=" * 80)
    print("📊 Final Results:")
    print(json.dumps(result, indent=2))
    print("=" * 80)
