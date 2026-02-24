import os
import sys
import time
import json
import subprocess
import argparse
import re
import csv
import shutil
from typing import Dict, Any, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datasets import load_dataset
from src.generator import generate_project
from src.utils.inference import InferenceManager
from src.utils.error_tracker import ErrorTracker
from src.utils.tools import ToolHandler
from src.utils.thread_memory import ThreadMemory
from src.docker.testing import DockerExecutor
from src.utils.prompt_manager import PromptManager


def find_solution_file(project_root: str) -> str:
    """Finds the main generated python file, ignoring tests and virtual environments."""
    python_files = []
    for root, _, files in os.walk(project_root):
        if '.alpha_stack' in root or '__pycache__' in root or 'venv' in root:
            continue
        for file in files:
            if file.endswith('.py') and not file.startswith('test_') and file != 'mbpp_runner.py':
                python_files.append(os.path.join(root, file))
                
    if not python_files:
        return None
        
    for pf in python_files:
        if 'solution.py' in pf or 'main.py' in pf:
            return pf
            
    return python_files[0]


def append_and_run_mbpp_tests(project_root: str, test_list: List[str]) -> Dict[str, Any]:
    solution_file = find_solution_file(project_root)
    if not solution_file:
         return {"success": False, "error": "No python source file found in generated project."}
         
    with open(solution_file, 'r', encoding='utf-8') as f:
        original_code = f.read()
        
    test_code = "\n\n# --- MBPP Hidden Tests ---\n"
    test_code += "if __name__ == '__main__':\n"
    test_code += "    pass_count = 0\n"
    for idx, test in enumerate(test_list):
        test_code += f"    try:\n"
        test_code += f"        {test}\n"
        test_code += f"        pass_count += 1\n"
        test_code += f"    except AssertionError:\n"
        test_code += f"        print('AssertionError on test: {test}')\n"
        test_code += f"    except Exception as e:\n"
        test_code += f"        print(f'Runtime Error on test {test}: {{e}}')\n"
        
    test_code += f"    print(f'Passed {{pass_count}} out of {len(test_list)} test cases')\n"
    
    runner_file = os.path.join(project_root, 'mbpp_runner.py')
    with open(runner_file, 'w', encoding='utf-8') as f:
        f.write(original_code + test_code)
        
    try:
        result = subprocess.run(["python", runner_file], capture_output=True, text=True, timeout=5, cwd=project_root)
        output = result.stdout + "\n" + result.stderr
        
        pattern = rf"Passed (\d+) out of {len(test_list)} test cases"
        match = re.search(pattern, output)
        if match:
            pass_count = int(match.group(1))
            success = pass_count == len(test_list)
            return {"success": success, "pass_count": pass_count, "total_count": len(test_list), "output": output}
        else:
            return {"success": False, "pass_count": 0, "total_count": len(test_list), "output": output, "error": "Parse error or crash"}
    except subprocess.TimeoutExpired:
        return {"success": False, "pass_count": 0, "total_count": len(test_list), "output": "Timeout after 5 seconds", "error": "Timeout"}


def run_eval_planner(project_root: str, mbpp_error: str, provider, max_loops: int = 3) -> bool:
    """A secondary feedback loop that attempts to fix the code using the MBPP error output."""
    print("[Eval Planner] Analyzing MBPP test failure...")
    
    pm = PromptManager()
    error_tracker = ErrorTracker(project_root)
    thread_memory = ThreadMemory(token_threshold=25000)
    image_name = "mbpp-eval-planner"
    
    docker_executor = DockerExecutor(project_root, image_name)
    tool_handler = ToolHandler(
        project_root, 
        error_tracker, 
        image_name, 
        agent_name="planner", 
        thread_memory=thread_memory,
        docker_executor=docker_executor
    )
    
    tools = provider.format_tools(InferenceManager.get_planner_tool_definitions())
    
    prompt = f"""You are the AlphaStack Eval Planner. Your job is to fix the generated code so it passes the hidden MBPP benchmark tests.
    
The code completely failed the MBPP hidden test cases.
Here is the execution output and the assertion error:
{mbpp_error}

Use the tools provided (`get_file_code`, `update_file_code`, `run_shell_command`) to fix the source code.
You have a maximum of {max_loops} tool calls.
Fix the logic in the main Python file to ensure that the assertions pass. Do not edit `mbpp_runner.py` directly, only edit the source code file.
"""
    
    messages = provider.create_initial_message(prompt)
    gave_up = False
    
    for _ in range(max_loops):
        response = provider.call_model(messages, tools=tools)
        function_calls = provider.extract_function_calls(response)
        if not function_calls:
            print("[Eval Planner] No more tool calls proposed. Ending loop.")
            break
            
        function_responses = []
        for fc in function_calls:
            func_name = fc["name"]
            func_args = fc.get("args", {})
            print(f"[Eval Planner] Calling {func_name}")
            result = tool_handler.handle_function_call(func_name, func_args)
            
            if isinstance(result, dict) and result.get("gave_up"):
                gave_up = True
                
            function_responses.append(provider.create_function_response(func_name, result, fc.get("id")))
            
        provider.accumulate_messages(messages, response, function_responses)
        if gave_up:
            print("[Eval Planner] Agent gave up. Ending loop.")
            break
            
    return True


def evaluate_mbpp(limit: int = None, offset: int = 0, provider_name: str = None):
    dataset = load_dataset("mbpp", "sanitized", split="test")
    
    try:
         if provider_name:
             provider = InferenceManager.initialize(provider_name, validate=True)
         else:
             provider = InferenceManager.initialize(validate=True)
    except Exception as e:
         print(f"Error initializing InferenceManager: {e}")
         return
         
    os.makedirs("eval_results", exist_ok=True)
    active_prov = InferenceManager._active_provider_name or provider_name or "default"
  
    model_name = provider.config.get("model", active_prov) if hasattr(provider, "config") else active_prov
    safe_model_name = model_name.replace("/", "-").replace(":", "-")
    
    metrics_file = f"mbpp_metrics_{safe_model_name}.csv"
    file_exists = os.path.exists(metrics_file)
    if not file_exists:
        with open(metrics_file, "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "task_id", "success", "pass_count", "total_count", 
                "time_taken_seconds", "tokens_used", "correction_loops", 
                "files_generated", "final_error"
            ])
            
    def status_callback(event_type, msg, **kwargs):
        pass
    end_idx = min(offset + limit, len(dataset)) if limit else len(dataset)
    for i in range(offset, end_idx):
        InferenceManager.reset_tokens()
        start_time = time.time()
        
        row = dataset[i]
        task_id = row['task_id']
        prompt_text = row.get('prompt', row.get('text', ''))
        test_list = row.get('test_list', [])
        challenge_test_list = row.get('challenge_test_list', [])
        all_tests = test_list + challenge_test_list
        
        print(f"\\n{'='*50}\\nEvaluating MBPP Task {task_id}\\n{'='*50}")
        project_dir = os.path.abspath(f"eval_results/mbpp_task_{task_id}")
        
        user_prompt = f"""Create a Python application with a highly optimized `solution.py` file. Implement the following function exactly as specified: {prompt_text}. You must also write comprehensive unit tests to verify this function works correctly for all edge cases.

Please use the EXACT following folder structure for your ASCII tree to ensure it parses correctly:
.
|-- Dockerfile
|-- pyproject.toml
|-- solution.py
|-- tests/
|   |-- test_solution.py
"""
        
        print(f"\\n>>> Phase 1: AlphaStack Project Generation & Testing")
        gen_result = generate_project(user_prompt, project_dir, on_status=status_callback, provider_name=provider_name)
        
        if not gen_result or not os.path.exists(project_dir):
            print(f"Task {task_id} failed to generate project.")
            with open(metrics_file, "a", newline='') as f:
                writer = csv.writer(f)
                writer.writerow([task_id, False, 0, len(all_tests), 0, 0, 0, 0, "Generation failed"])
            if os.path.exists(project_dir):
                shutil.rmtree(project_dir)
            continue
        num_files = 0
        for root, _, files in os.walk(project_dir):
            if '.alpha_stack' in root or '__pycache__' in root:
                continue
            for file in files:
                if os.path.getsize(os.path.join(root, file)) > 0:
                    num_files += 1
        
        print(f"\\n>>> Phase 2: Hidden MBPP Tests Verification")
        test_result = append_and_run_mbpp_tests(project_dir, all_tests)
        success = test_result.get("success", False)
        pass_count = test_result.get("pass_count", 0)
        correction_loops = 0
        
        if not success:
            print(f"\\n>>> Phase 3: Tests Failed ({pass_count}/{len(all_tests)}). Initiating Eval Planner Feedback Loop")
            error_output = test_result.get("output", "Unknown error")
            run_eval_planner(project_dir, error_output, provider, max_loops=3)
            correction_loops += 1
            
            print(f"\\n>>> Phase 4: Re-evaluating after Eval Planner corrections")
            test_result = append_and_run_mbpp_tests(project_dir, all_tests)
            success = test_result.get("success", False)
            pass_count = test_result.get("pass_count", 0)
            
        end_time = time.time()
        time_taken = end_time - start_time
        tokens_used = InferenceManager.get_total_tokens()
        with open(metrics_file, "a", newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                task_id,
                success,
                pass_count,
                len(all_tests),
                round(time_taken, 2),
                tokens_used,
                correction_loops,
                num_files,
                None if success else test_result.get("error", "Failed")
            ])
            
        print(f"\\n>>> Result for Task {task_id}: {'SUCCESS' if success else 'FAILED'} (Time: {time_taken:.2f}s, Tokens: {tokens_used}, Files: {num_files})")

        print(f"Cleaning up {project_dir}...")
        try:
             shutil.rmtree(project_dir)
        except Exception as e:
             print(f"Warning: Failed to delete {project_dir}: {e}")
             
    print(f"\\nEvaluations finished. Metrics saved to {metrics_file}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Number of problems to run")
    parser.add_argument("--offset", type=int, default=0, help="Offset index")
    parser.add_argument("--provider", type=str, default=None, help="Provider to use (e.g. openai, google, openrouter)")
    args = parser.parse_args()
    evaluate_mbpp(limit=args.limit, offset=args.offset, provider_name=args.provider)
