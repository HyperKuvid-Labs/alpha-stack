import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from datasets import load_dataset
import os
import subprocess

def extract_code(gc):
  # extract code from the generated text
  # we can use regex to extract the code between ```python and ```
  import re

  solution_pattern = r"# BEGIN SOLUTION(.*?)# END SOLUTION"
  solution_match = re.search(solution_pattern, gc, re.DOTALL)
  if solution_match:
    return solution_match.group(1).strip()

  pattern = r"```python(.*?)```"
  match = re.search(pattern, gc, re.DOTALL)
  if match:
    return match.group(1).strip()

  solution_label_pattern = r"Solution:\s*(.*)"
  solution_label_match = re.search(solution_label_pattern, gc, re.DOTALL | re.IGNORECASE)
  if solution_label_match:
    return solution_label_match.group(1).strip()

  code_start = re.search(r'^(import|def|from)', gc, re.MULTILINE)
  if code_start:
      return gc[code_start.start():].strip()

  return gc.strip()

def extract_result(output):
  # extract the result from the output, we can look for the line that starts with "Passed" and extract the numbers
  import re
  pattern = r"Passed (\d+) out of (\d+) test cases"
  match = re.search(pattern, output)
  if match:
    pass_count = int(match.group(1))
    total_count = int(match.group(2))
    return pass_count, total_count
  else:
    return 0, 0

def check_main(gc):
  # check if the generated code has a main block that runs the tests
  return "if __name__ == \"__main__\""  and "def main():" in gc

def add_main_block(gc, test_cases, function_name):
  # test_cases come from the dataset and include METADATA and def check(candidate): with assert statements
  # we need to extract just the assert statements, replace candidate with function_name, and create a proper test runner

  import re

  # remove the METADATA block
  test_cases = re.sub(r'METADATA\s*=\s*\{[^}]*\}', '', test_cases, flags=re.DOTALL)

  # extract all assert statements from the check function
  assert_pattern = r'assert\s+(.+?)(?=\n|$)'
  assertions = re.findall(assert_pattern, test_cases, re.DOTALL)

  # count total test cases
  total_count = len(assertions)

  # create the test runner
  test_code = "\n# test runner to check all test cases\n"
  test_code += "if __name__ == \"__main__\":\n"
  test_code += "    pass_count = 0\n"
  test_code += f"    total_count = {total_count}\n"
  test_code += "    \n"

  # add each test case with try-except to count passes
  for idx, assertion in enumerate(assertions):
    # replace candidate with the actual function name
    assertion = assertion.replace("candidate", function_name)
    test_code += f"    # test case {idx + 1}\n"
    test_code += "    try:\n"
    test_code += f"        assert {assertion.strip()}\n"
    test_code += "        pass_count += 1\n"
    test_code += "    except AssertionError:\n"
    test_code += "        pass\n"
    test_code += "    \n"

  # add the final print statement
  test_code += "    print(f\"Passed {pass_count} out of {total_count} test cases\")\n"

  return gc + "\n" + test_code

def evaulate_model_on_humaneval(model_name):
  # model id, for now: Qwen/Qwen3-4B
  device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
  tokenizer = AutoTokenizer.from_pretrained(model_name)
  model = AutoModelForCausalLM.from_pretrained(model_name).to(device)

  dataset = load_dataset("openai/openai_humaneval", split="test")

  # dataset has these columns -> task_id, prompt, canonical_solution, test, entry_point we can ignore canonical_solution and entry_point for now
  # my idea is to generate the whole code from the prompt, save it and then run the test cases on it and see if it passes or not

  # prompt format
  # from typing import List


  # def has_close_elements(numbers: List[float], threshold: float) -> bool:
  # """ Check if in given list of numbers, are any two numbers closer to each other than
  # given threshold.
  # >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
  # False
  # >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
  # True
  # """

  # test format
  # METADATA = {
  # 'author': 'jt',
  # 'dataset': 'test'
  # }


  # def check(candidate):
  # assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True
  # assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False
  # assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.95) == True
  # assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.8) == False
  # assert candidate([1.0, 2.0, 3.0, 4.0, 5.0, 2.0], 0.1) == True
  # assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 1.0) == True
  # assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 0.5) == False

  os.makedirs("temp_test", exist_ok=True)

  count_passed = 0

  for i in range(len(dataset)):
    _, prompt, _, test_cases, _ = dataset[i].values()
    full_prompt = f"""# Task: Complete the Python function and run the tests.
      # Return ONLY the code.

      {prompt}
          # Implementation goes here
          pass

      {test_cases}

      if __name__ == "__main__":
          try:
              check({dataset[i]['entry_point']})
              # If no assertion error, all tests passed.
              # HumanEval 'test' strings usually contain multiple asserts.
              # We will wrap the 'check' function to count successes.
              print("Passed 1 out of 1 test cases")
          except Exception as e:
              print("Passed 0 out of 1 test cases")
      """
    inputs = tokenizer(full_prompt, return_tensors="pt").to(device)
    outputs = model.generate(**inputs, max_length=2046, temperature=0.1, top_p=0.95)
    # print(f"outputs: {outputs}")
    generated_code = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # print(f"Generated code for problem {i}:\n{generated_code}\n{'-'*50}")

    with open(f"temp_test/test_{i}.py", "w") as f:
      generated_code = extract_code(generated_code)
      x = check_main(generated_code)
      function_name = dataset[i]['entry_point']
      if not x:
        generated_code = add_main_block(generated_code, test_cases, function_name)
      f.write(generated_code)

    # need to run the generated code and check how many test cases pass, we can use subprocess to run the code and capture the output
    # add a timeout of 5 seconds to prevent infinite loops or hanging code
    try:
      result = subprocess.run(["python", f"temp_test/test_{i}.py"], capture_output=True, text=True, timeout=5)
      print(result.stdout)
      if result.stderr:
        print(f"Error output: {result.stderr}")
    except subprocess.TimeoutExpired:
      print("Test execution timed out after 5 seconds")
      result = None

    # extract the result and check if all test cases passed
    if result:
      res = extract_result(result.stdout)
      if res:
        pass_count, total_count = res
        if pass_count == total_count and total_count > 0:
          count_passed += 1

  print(f"Model {model_name} passed {count_passed} out of {len(dataset)} problems")

if __name__ == "__main__":
  model_name = "Qwen/Qwen2.5-Coder-7B-Instruct"
  evaulate_model_on_humaneval(model_name)
