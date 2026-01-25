import os
import json
import re
import select
import subprocess
from typing import Dict, List, Optional, Tuple
from ..utils.helpers import (
    get_client, retry_api_call, build_project_structure_tree, MODEL_NAME, prime_intellect_client
)
from ..utils.prompt_manager import PromptManager
from ..utils.error_tracker import ErrorTracker
from ..utils.tools import ToolHandler
from ..utils.command_log import CommandLogManager
from ..agents.planner import PlanningAgent
from ..agents.corrector import CorrectionAgent
from .generator import generate_dockerignore_content


class CommandExecutor:
    def __init__(self, project_root: str, error_tracker: Optional[ErrorTracker] = None,
                 docker_image: str = "project-test", use_docker: bool = True,
                 command_log_manager: Optional[CommandLogManager] = None,
                 docker_network: str = "bridge",
                 memory_pct: float = 0.25,
                 cpu_pct: float = 0.5):
        self.project_root = project_root
        self.error_tracker = error_tracker
        self.command_log_manager = command_log_manager or CommandLogManager(project_root)
        self.executed_commands = []
        self.docker_image = docker_image
        self.use_docker = use_docker
        self.docker_network = docker_network
        self.memory_pct = memory_pct
        self.cpu_pct = cpu_pct

    def _compute_docker_resources(self) -> Tuple[str, str, str, str]:
        try:
            page_size = os.sysconf('SC_PAGE_SIZE')
            pages = os.sysconf('SC_PHYS_PAGES')
            total_mem = page_size * pages
        except Exception:
            total_mem = 8 * 1024**3

        mem_bytes = int(total_mem * max(0.01, min(1.0, self.memory_pct)))
        mem_mb = max(4, mem_bytes // (1024**2))
        memory_str = f"{mem_mb}m"
        memory_swap_str = memory_str

        cpus = os.cpu_count() or 1
        cpu_value = max(0.1, round(cpus * max(0.01, min(1.0, self.cpu_pct)), 2))
        cpu_str = str(cpu_value)

        network = self.docker_network

        return memory_str, memory_swap_str, cpu_str, network

    def _check_docker_image_exists(self) -> bool:
        try:
            check_result = subprocess.run(
                ['docker', 'images', '-q', self.docker_image],
                capture_output=True,
                text=True,
                shell=False
            )
            return bool(check_result.stdout.strip())
        except Exception:
            return False

    def execute_command(self, command: List[str], description: str = "",
                       cwd: Optional[str] = None, timeout: int = 300) -> Tuple[bool, str]:
        if not command:
            return False, "Empty command"

        command_str = " ".join(command)

        if self.use_docker and self._check_docker_image_exists():
            return self._execute_in_docker(command, command_str, description, timeout)
        else:
            return self._execute_on_host(command, command_str, description, cwd, timeout)

    def _execute_in_docker(self, command: List[str], command_str: str,
                          description: str, timeout: int) -> Tuple[bool, str]:
        try:
            def escape_shell_arg(arg):
                return f"'{arg.replace(chr(39), chr(39) + chr(34) + chr(39) + chr(34) + chr(39))}'"
            escaped_command = " ".join(escape_shell_arg(arg) for arg in command)

            memory_str, memory_swap_str, cpu_str, network_mode = self._compute_docker_resources()

            docker_args = [
                'docker', 'run',
                '--rm',
                '--network', network_mode,
                '--tmpfs', '/tmp:rw,noexec,nosuid',
                '--tmpfs', '/run:rw,noexec,nosuid',
                '--tmpfs', '/app/.pytest_cache:rw',
                '--user', '1000:1000',
                '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges',
                '--memory', memory_str,
                '--memory-swap', memory_swap_str,
                '--cpus', cpu_str,
                '--pids-limit', '500',
                '--log-driver', 'none',
                self.docker_image,
                'sh', '-c', escaped_command
            ]

            result = subprocess.run(
                docker_args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )

            combined_output = result.stdout + "\n" + result.stderr

            self.command_log_manager.log_command(
                command=command_str,
                description=description,
                success=result.returncode == 0,
                logs=combined_output,
                returncode=result.returncode,
                executed_in="docker"
            )

            self.executed_commands.append({
                "command": command_str,
                "description": description,
                "success": result.returncode == 0,
                "logs": combined_output,
                "returncode": result.returncode,
                "executed_in": "docker"
            })

            if self.error_tracker:
                self.error_tracker.log_change(
                    file_path="",
                    change_description=f"Executed command in Docker: {command_str}",
                    error=combined_output if result.returncode != 0 else "",
                    actions=[f"execute_command:{command_str}"]
                )

            return result.returncode == 0, combined_output

        except subprocess.TimeoutExpired:
            error_msg = f"Command timeout after {timeout} seconds"
            self.executed_commands.append({
                "command": command_str,
                "description": description,
                "success": False,
                "logs": error_msg,
                "returncode": -1,
                "executed_in": "docker"
            })
            return False, error_msg
        except Exception as e:
            error_msg = f"Command execution error: {str(e)}"
            self.executed_commands.append({
                "command": command_str,
                "description": description,
                "success": False,
                "logs": error_msg,
                "returncode": -1,
                "executed_in": "docker"
            })
            return False, error_msg

    def _execute_on_host(self, command: List[str], command_str: str,
                        description: str, cwd: Optional[str], timeout: int) -> Tuple[bool, str]:
        cwd = cwd or self.project_root

        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )

            combined_output = result.stdout + "\n" + result.stderr

            self.command_log_manager.log_command(
                command=command_str,
                description=description,
                success=result.returncode == 0,
                logs=combined_output,
                returncode=result.returncode,
                executed_in="host"
            )

            self.executed_commands.append({
                "command": command_str,
                "description": description,
                "success": result.returncode == 0,
                "logs": combined_output,
                "returncode": result.returncode,
                "executed_in": "host"
            })

            if self.error_tracker:
                self.error_tracker.log_change(
                    file_path="",
                    change_description=f"Executed command on host: {command_str}",
                    error=combined_output if result.returncode != 0 else "",
                    actions=[f"execute_command:{command_str}"]
                )

            return result.returncode == 0, combined_output

        except subprocess.TimeoutExpired:
            error_msg = f"Command timeout after {timeout} seconds"
            self.executed_commands.append({
                "command": command_str,
                "description": description,
                "success": False,
                "logs": error_msg,
                "returncode": -1
            })
            return False, error_msg

        except Exception as e:
            error_msg = f"Command execution error: {str(e)}"
            self.executed_commands.append({
                "command": command_str,
                "description": description,
                "success": False,
                "logs": error_msg,
                "returncode": -1
            })
            return False, error_msg

    def execute_command_sequence(self, commands: List[Dict],
                                 stop_on_failure: bool = True) -> Tuple[bool, List[Dict]]:
        results = []
        all_succeeded = True

        for cmd_info in commands:
            step = cmd_info.get("step", "unknown")
            description = cmd_info.get("description", "")
            command = cmd_info.get("command", [])

            if not command:
                continue

            success, logs = self.execute_command(command, description)

            result = {
                "step": step,
                "description": description,
                "command": command,
                "success": success,
                "logs": logs
            }
            results.append(result)

            if not success:
                all_succeeded = False
                if stop_on_failure:
                    break

        return all_succeeded, results

    def get_execution_logs(self) -> str:
        return self.command_log_manager.get_formatted_history_for_planning(max_tokens=10000)


class LogSummarizerAgent:
    def __init__(self):
        self.client = prime_intellect_client()

    def summarize_commands(self, commands: List[Dict]) -> str:
        if not commands:
            return ""

        prompt = self._build_summarization_prompt(commands)

        try:
            messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt

            response = retry_api_call(
                self.client.chat.completions.create,
                model="models/gemini-2.5-flash",
                messages=messages
            )

            response = response.choices[0].message.content
            summary = response.strip()

            if summary.startswith('```'):
                lines = summary.split('\n')
                if len(lines) > 1:
                    summary = '\n'.join(lines[1:])
                    if summary.endswith('```'):
                        summary = summary[:-3].rstrip()

            return summary
        except Exception:
            return self._fallback_summary(commands)

    def _build_summarization_prompt(self, commands: List[Dict]) -> str:
        prompt = """Summarize these command executions in a single text block. For each command, include:
1. Command executed
2. Output log (key parts only, not full output - focus on errors, warnings, or important success messages)
3. Status (PASSED/FAILED/PARTIAL SUCCESS)
4. Important output or errors

Format as plain text, one command per section. Keep it concise but informative.

Command executions:
"""

        for i, cmd in enumerate(commands):
            prompt += f"\n[Command {i+1}]\n"
            prompt += f"Command: {cmd.get('command', '')}\n"
            if cmd.get('description'):
                prompt += f"Description: {cmd.get('description')}\n"
            prompt += f"Output:\n{cmd.get('logs', '')[:2000]}\n"
            prompt += f"Success: {cmd.get('success', False)}\n"
            prompt += f"Exit Code: {cmd.get('returncode', -1)}\n"

        prompt += "\n\nProvide a concise summary in the format specified above."

        return prompt

    def _fallback_summary(self, commands: List[Dict]) -> str:
        summary_lines = []
        summary_lines.append(f"Executed {len(commands)} commands:\n")

        for cmd in commands:
            summary_lines.append(f"- Command: {cmd.get('command', '')}")
            if cmd.get('description'):
                summary_lines.append(f"  Description: {cmd.get('description')}")

            logs = cmd.get('logs', '')
            if logs:
                lines = logs.split('\n')
                for line in lines:
                    if any(keyword in line.lower() for keyword in ['error', 'failed', 'exception']):
                        summary_lines.append(f"  Output: {line[:150]}")
                        break
                else:
                    for line in lines[-5:]:
                        if any(keyword in line.lower() for keyword in ['passed', 'success', 'ok']):
                            summary_lines.append(f"  Output: {line[:150]}")
                            break

            if cmd.get('success'):
                summary_lines.append(f"  Status: PASSED")
            else:
                summary_lines.append(f"  Status: FAILED (exit code: {cmd.get('returncode', -1)})")

            summary_lines.append("")

        return "\n".join(summary_lines)


class DockerTestingPipeline:
    DEPENDENCY_FILE_PATTERNS = {
        'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'bun.lockb',
        'requirements.txt', 'requirements-dev.txt', 'requirements-test.txt',
        'Pipfile', 'Pipfile.lock', 'pyproject.toml', 'poetry.lock', 'setup.py', 'setup.cfg',
        'Cargo.toml', 'Cargo.lock', 'go.mod', 'go.sum',
        'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'gradle.properties',
        'composer.json', 'composer.lock',
        'Gemfile', 'Gemfile.lock',
        'mix.exs', 'mix.lock',
        'pubspec.yaml', 'pubspec.lock',
        'CMakeLists.txt', 'Makefile', 'makefile', 'conanfile.txt', 'vcpkg.json',
        'rebar.config', 'rebar.lock',
        'Dockerfile', '.dockerignore',
        'tsconfig.json', 'vite.config.js', 'vite.config.ts', 'webpack.config.js',
        'hardhat.config.js', 'hardhat.config.ts', 'truffle-config.js', 'foundry.toml',
    }

    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict, pm: Optional[PromptManager] = None,
                 error_tracker: Optional[ErrorTracker] = None,
                 dependency_analyzer=None, on_status=None,
                 docker_network: str = "bridge",
                 docker_memory_pct: float = 0.25,
                 docker_cpu_pct: float = 0.5):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.pm = pm or PromptManager(templates_dir="prompts")
        self.max_iterations = 10
        self.dockerfile_path = os.path.join(project_root, "Dockerfile")
        self.dependency_analyzer = dependency_analyzer
        self.on_status = on_status
        self.docker_network = docker_network
        self.docker_memory_pct = docker_memory_pct
        self.docker_cpu_pct = docker_cpu_pct

        project_name = os.path.basename(os.path.normpath(project_root))
        self.image_name = re.sub(r'[^a-z0-9-]', '-', project_name.lower())

        self.error_tracker = error_tracker or ErrorTracker(project_root)
        self.tool_handler = ToolHandler(project_root, self.error_tracker, image_name=self.image_name)

        self.command_log_manager = CommandLogManager(project_root)
        self.log_summarizer = LogSummarizerAgent()

        self.planning_agent = PlanningAgent(
            project_root=project_root,
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            file_output_format=self.file_output_format,
            pm=self.pm,
            error_tracker=self.error_tracker,
            tool_handler=self.tool_handler,
            command_log_manager=self.command_log_manager
        )

        self.correction_agent = CorrectionAgent(
            project_root=project_root,
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            file_output_format=self.file_output_format,
            pm=self.pm,
            error_tracker=self.error_tracker,
            tool_handler=self.tool_handler
        )

        self.command_executor = CommandExecutor(
            project_root,
            self.error_tracker,
            docker_image=self.image_name,
            command_log_manager=self.command_log_manager,
            docker_network=self.docker_network,
            memory_pct=self.docker_memory_pct,
            cpu_pct=self.docker_cpu_pct
        )

        self.dependency_feedback_loop = None

    def _emit(self, event_type: str, message: str, **kwargs):
        if self.on_status:
            self.on_status(event_type, message, **kwargs)

    def _is_dependency_file(self, filepath: str) -> bool:
        if not filepath:
            return False
        filename = os.path.basename(filepath)
        if filename in self.DEPENDENCY_FILE_PATTERNS:
            return True
        if filename.endswith(('.csproj', '.fsproj', '.vbproj', '.sln', '.gemspec')):
            return True
        return False

    def _fix_plan_requires_rebuild(self, fix_plan: List[Dict]) -> bool:
        for fix in fix_plan:
            filepath = fix.get('filepath', '') or fix.get('file', '')
            if self._is_dependency_file(filepath):
                return True
        return False

    def _reanalyze_changed_files(self, fix_plan: List[Dict]) -> None:
        if not self.dependency_analyzer:
            return

        changed_files = set()
        for fix in fix_plan:
            filepath = fix.get('filepath', '') or fix.get('file', '')
            if filepath:
                if not os.path.isabs(filepath):
                    filepath = os.path.join(self.project_root, filepath)
                if os.path.exists(filepath):
                    changed_files.add(filepath)

        if not changed_files:
            return

        for file_path in changed_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.dependency_analyzer.add_file(file_path, content, self.folder_structure)
            except Exception:
                pass

    def _check_coupling_for_changed_files(self, fix_plan: List[Dict]) -> List[Dict]:
        if not self.dependency_feedback_loop or not self.dependency_analyzer:
            return []

        changed_files = set()
        for fix in fix_plan:
            filepath = fix.get('filepath', '') or fix.get('file', '')
            if filepath:
                if not os.path.isabs(filepath):
                    filepath = os.path.join(self.project_root, filepath)
                if os.path.exists(filepath):
                    changed_files.add(filepath)

        if not changed_files:
            return []

        files_to_check = set(changed_files)
        for changed_file in changed_files:
            try:
                dependents = self.dependency_analyzer.get_dependents(changed_file)
                files_to_check.update(dependents)
            except Exception:
                pass

        all_coupling_errors = []
        for file_path in files_to_check:
            if not os.path.exists(file_path):
                continue

            try:
                errors = self.dependency_feedback_loop.check_file_dependencies(file_path)

                if errors:
                    for error in errors:
                        all_coupling_errors.append(error.to_dict(self.project_root))
            except Exception:
                pass

        return all_coupling_errors

    def build_docker_image(self) -> Tuple[bool, str]:
        try:
            # Use BuildKit with plain progress for better output streaming
            env = os.environ.copy()
            env['DOCKER_BUILDKIT'] = '1'

            # Stream output in real-time while also capturing it
            process = subprocess.Popen(
                ['docker', 'build', '--progress=plain', '-t', self.image_name, '.'],
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )

            output_lines = []
            try:
                # Stream output line by line with timeout handling
                while True:
                    # Check if process has finished
                    if process.poll() is not None:
                        # Read any remaining output
                        remaining = process.stdout.read()
                        if remaining:
                            output_lines.append(remaining)
                            self._emit("docker_build", remaining.strip())
                        break

                    # Read available output (non-blocking on Unix)
                    if hasattr(select, 'select'):
                        readable, _, _ = select.select([process.stdout], [], [], 1.0)
                        if readable:
                            line = process.stdout.readline()
                            if line:
                                output_lines.append(line)
                                self._emit("docker_build", line.strip())
                    else:
                        # Fallback for Windows
                        line = process.stdout.readline()
                        if line:
                            output_lines.append(line)
                            self._emit("docker_build", line.strip())
                        elif process.poll() is not None:
                            break

                # Wait for process to complete with timeout
                process.wait(timeout=600)

            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                return False, "Docker build timeout (exceeded 10 minutes)"

            combined_output = "".join(output_lines)

            if process.returncode == 0:
                return True, combined_output
            else:
                return False, combined_output

        except Exception as e:
            return False, f"Docker build error: {str(e)}"

    def generate_dockerfile(self) -> bool:
        try:
            project_structure_tree = build_project_structure_tree(self.project_root)

            prompt = self.pm.render("dockerfile_generation.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                file_summaries={},
                external_dependencies=[],
                project_root=self.project_root,
                project_structure_tree=project_structure_tree
            )

            client = prime_intellect_client()
            messages = [
                {"role": "user", "content": prompt}
            ] if isinstance(prompt, str) else prompt

            response = retry_api_call(
                client.chat.completions.create,
                model=MODEL_NAME,
                messages=messages
            )

            response = response.choices[0].message.content
            dockerfile_content = response.strip()

            if dockerfile_content.startswith('```'):
                lines = dockerfile_content.split('\n')
                if len(lines) > 1:
                    dockerfile_content = '\n'.join(lines[1:])
                    if dockerfile_content.endswith('```'):
                        dockerfile_content = dockerfile_content[:-3].rstrip()

            with open(self.dockerfile_path, 'w', encoding='utf-8') as f:
                f.write(dockerfile_content)

            # Generate .dockerignore to speed up builds
            dockerignore_path = os.path.join(self.project_root, ".dockerignore")
            with open(dockerignore_path, 'w', encoding='utf-8') as f:
                f.write(generate_dockerignore_content())

            if self.error_tracker:
                self.error_tracker.log_change(
                    file_path=self.dockerfile_path,
                    change_description="Generated Dockerfile and .dockerignore from software blueprint",
                    error_context="Dockerfile generation phase",
                    actions=["generate_dockerfile", "generate_dockerignore"]
                )

            return True

        except Exception:
            return False

    def run_tests_in_docker(self) -> Tuple[bool, str]:
        try:
            test_command = self._get_test_command()

            memory_str, memory_swap_str, cpu_str, network_mode = self.command_executor._compute_docker_resources()

            docker_args = [
                'docker', 'run',
                '--rm',
                '--network', network_mode,
                '--read-only',
                '--tmpfs', '/tmp:rw,noexec,nosuid',
                '--tmpfs', '/run:rw,noexec,nosuid',
                '--tmpfs', '/app/.pytest_cache:rw',
                '--user', '1000:1000',
                '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges',
                '--memory', memory_str,
                '--memory-swap', memory_swap_str,
                '--cpus', cpu_str,
                '--pids-limit', '100',
                '--log-driver', 'none',
                self.image_name
            ] + test_command

            result = subprocess.run(
                docker_args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600
            )

            full_logs = result.stdout + "\n" + result.stderr

            if result.returncode == 0:
                return True, full_logs
            else:
                return False, full_logs

        except subprocess.TimeoutExpired:
            return False, "Test timeout (2 minutes)"
        except Exception as e:
            return False, f"Test error: {str(e)}"

    def _detect_test_command_with_agent(self) -> List[str]:
        try:
            project_structure_tree = build_project_structure_tree(self.project_root)

            test_files = []
            test_dirs = ['tests', 'test', '__tests__']
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for file in files:
                    if file.startswith('test_') or file.endswith('_test.py') or file.endswith('_test.js') or file.endswith('_test.ts'):
                        rel_path = os.path.relpath(os.path.join(root, file), self.project_root)
                        test_files.append(rel_path)

                dir_name = os.path.basename(root)
                if dir_name in test_dirs:
                    for file in files:
                        if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')) and not file.startswith('.'):
                            rel_path = os.path.relpath(os.path.join(root, file), self.project_root)
                            if rel_path not in test_files:
                                test_files.append(rel_path)

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
                test_files=test_files[:50],
                config_files=config_files[:20],
                project_root=self.project_root
            )

            client = prime_intellect_client()
            messages = [
                {"role": "user", "content": prompt}
            ] if isinstance(prompt, str) else prompt

            response = retry_api_call(
                client.chat.completions.create,
                model=MODEL_NAME,
                messages=messages
            )

            response = response.choices[0].message.content
            response_text = response.strip()

            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    command = result.get("command", [])

                    if command and isinstance(command, list):
                        command = [str(arg) for arg in command if arg]
                        if command:
                            return command
                    elif command and isinstance(command, str):
                        command_list = command.split()
                        if command_list:
                            return command_list
                except json.JSONDecodeError:
                    pass

            return ["pytest", "-v"]
        except Exception:
            return ["pytest", "-v"]

    def _get_test_command(self) -> List[str]:
        command = self._detect_test_command_with_agent()

        if self.error_tracker:
            self.error_tracker.log_change(
                file_path="",
                change_description=f"Detected test command: {' '.join(command)}",
                error_context="Test command detection",
                actions=["detect_test_command"]
            )

        return command

    def _check_and_summarize_logs(self):
        if not self.command_log_manager:
            return

        token_count = self.command_log_manager.get_token_count()
        threshold = 8000

        if token_count > threshold:
            all_commands = self.command_log_manager.commands
            if len(all_commands) <= 1:
                return

            last_command = all_commands[-1]
            older_commands = all_commands[:-1]

            summary = self.log_summarizer.summarize_commands(older_commands)

            self.command_log_manager.last_summary = summary
            self.command_log_manager.commands = [last_command]
            self.command_log_manager.save_to_file()

    def run_testing_pipeline(self) -> Dict:
        results = {
            "build_success": False,
            "runtime_success": False,
            "tests_success": False,
            "build_iterations": 0,
            "runtime_iterations": 0,
            "test_iterations": 0,
            "success": False
        }

        if not os.path.exists(self.dockerfile_path):
            return {
                **results,
                "message": "Dockerfile not found. Ensure docker_test_gen.py generates it first."
            }

        build_iteration = 0
        previous_build_errors = set()
        stuck_build_iterations = 0
        max_stuck_iterations = 10

        while build_iteration < self.max_iterations:
            build_iteration += 1

            success, build_logs = self.build_docker_image()

            if success:
                results["build_success"] = True
                results["build_iterations"] = build_iteration
                break

            fix_plan = self.planning_agent.plan_fixes(logs=build_logs, error_type="build")

            self._check_and_summarize_logs()

            if not fix_plan:
                continue

            current_fix_signatures = {
                (f.get("filepath", ""), f.get("error", "")[:100]) for f in fix_plan
            }

            if current_fix_signatures == previous_build_errors:
                stuck_build_iterations += 1

                if stuck_build_iterations >= max_stuck_iterations:
                    break
            else:
                stuck_build_iterations = 0
                previous_build_errors = current_fix_signatures

            fixes_applied = 0
            for i, error_info in enumerate(fix_plan, 1):
                commands = error_info.get("commands", [])
                if commands:
                    for cmd in commands:
                        if isinstance(cmd, list) and cmd:
                            success, cmd_logs = self.command_executor.execute_command(
                                cmd,
                                description=f"Command suggested by planner: {' '.join(cmd)}"
                            )
                            if not success:
                                error_info["command_logs"] = cmd_logs

                if self.correction_agent.fix_error(error_info):
                    fixes_applied += 1
                    self.planning_agent.invalidate_cache()
                    self.correction_agent.invalidate_cache()

            if fixes_applied == 0:
                continue

            self._reanalyze_changed_files(fix_plan)

            coupling_errors = self._check_coupling_for_changed_files(fix_plan)
            if coupling_errors:
                for coupling_error in coupling_errors:
                    if self.correction_agent.fix_error(coupling_error):
                        self.planning_agent.invalidate_cache()
                        self.correction_agent.invalidate_cache()
                self._reanalyze_changed_files(fix_plan)

        if not results["build_success"]:
            return {
                **results,
                "message": "Docker build failed after maximum iterations"
            }

        results["runtime_success"] = True
        results["runtime_iterations"] = 0

        test_iteration = 0
        test_logs = ""
        previous_test_errors = set()
        stuck_test_iterations = 0

        while test_iteration < self.max_iterations:
            test_iteration += 1

            success, test_logs = self.run_tests_in_docker()

            if success:
                results["tests_success"] = True
                results["test_iterations"] = test_iteration
                break

            fix_plan = self.planning_agent.plan_fixes(logs=test_logs, error_type="test")

            self._check_and_summarize_logs()

            if not fix_plan:
                continue

            current_fix_signatures = {
                (f.get("filepath", ""), f.get("error", "")[:100]) for f in fix_plan
            }

            if current_fix_signatures == previous_test_errors:
                stuck_test_iterations += 1

                if stuck_test_iterations >= max_stuck_iterations:
                    break
            else:
                stuck_test_iterations = 0
                previous_test_errors = current_fix_signatures

            fixes_applied = 0
            for i, error_info in enumerate(fix_plan, 1):
                commands = error_info.get("commands", [])
                if commands:
                    for cmd in commands:
                        if isinstance(cmd, list) and cmd:
                            success, cmd_logs = self.command_executor.execute_command(
                                cmd,
                                description=f"Command suggested by planner: {' '.join(cmd)}"
                            )
                            if not success:
                                error_info["command_logs"] = cmd_logs

                if self.correction_agent.fix_error(error_info):
                    fixes_applied += 1
                    self.planning_agent.invalidate_cache()
                    self.correction_agent.invalidate_cache()

            if fixes_applied == 0:
                continue

            self._reanalyze_changed_files(fix_plan)

            coupling_errors = self._check_coupling_for_changed_files(fix_plan)
            if coupling_errors:
                for coupling_error in coupling_errors:
                    if self.correction_agent.fix_error(coupling_error):
                        self.planning_agent.invalidate_cache()
                        self.correction_agent.invalidate_cache()
                self._reanalyze_changed_files(fix_plan)

            if self._fix_plan_requires_rebuild(fix_plan):
                rebuild_success, rebuild_logs = self.build_docker_image()
                if not rebuild_success:
                    continue

        results["success"] = results["build_success"] and results["tests_success"]

        if results["success"]:
            results["message"] = "All pipeline steps successful: Build ✅ Tests ✅"
        else:
            results["message"] = f"Pipeline incomplete: Build {'✅' if results['build_success'] else '❌'} Tests {'✅' if results['tests_success'] else '❌'}"
            if test_logs:
                results["test_logs"] = test_logs[-1000:]

        return results


def run_docker_testing(project_root: str, software_blueprint: Dict,
                      folder_structure: str, file_output_format: Dict,
                      pm=None, error_tracker=None, dependency_analyzer=None,
                      on_status=None, docker_network: str = "bridge",
                      docker_memory_pct: float = 0.25,
                      docker_cpu_pct: float = 0.5) -> Dict:
    pipeline = DockerTestingPipeline(
        project_root=project_root,
        software_blueprint=software_blueprint,
        folder_structure=folder_structure,
        file_output_format=file_output_format,
        pm=pm,
        error_tracker=error_tracker,
        dependency_analyzer=dependency_analyzer,
        on_status=on_status,
        docker_network=docker_network,
        docker_memory_pct=docker_memory_pct,
        docker_cpu_pct=docker_cpu_pct
    )
    return pipeline.run_testing_pipeline()

