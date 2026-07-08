"""External oracle checks: execution, agent-facing formatting, gaming detection."""

from src.utils.oracle import format_failures_for_agent, gaming_suspected, run_checks


def test_check_passes_on_output_and_exit(tmp_path):
    results = run_checks(str(tmp_path), [
        {"name": "hello", "cmd": "echo hello world", "expected_output": "hello", "expected_exit": 0},
    ])
    assert results[0]["passed"] is True


def test_check_fails_on_wrong_output(tmp_path):
    results = run_checks(str(tmp_path), [
        {"name": "wrong", "cmd": "echo actual", "expected_output": "expected-value"},
    ])
    assert results[0]["passed"] is False
    assert "actual" in results[0]["output_tail"]


def test_check_fails_on_exit_code(tmp_path):
    results = run_checks(str(tmp_path), [
        {"name": "exit", "cmd": "exit 3", "expected_exit": 0},
    ])
    assert results[0]["passed"] is False
    assert results[0]["exit_code"] == 3


def test_check_without_expectations_is_invalid(tmp_path):
    results = run_checks(str(tmp_path), [{"name": "bad", "cmd": "echo hi"}])
    assert results[0]["passed"] is False
    assert "error" in results[0]


def test_hidden_failures_never_reach_the_agent(tmp_path):
    results = run_checks(str(tmp_path), [
        {"name": "public_fail", "cmd": "echo a", "expected_output": "zzz"},
        {"name": "hidden_fail", "cmd": "echo b", "expected_output": "SECRET-42", "hidden": True},
    ])
    report = format_failures_for_agent(results)
    assert "public_fail" in report
    assert "hidden_fail" not in report
    assert "SECRET-42" not in report


def test_gaming_signature():
    # Public all pass, hidden sibling fails -> hardcoding suspected.
    assert gaming_suspected([
        {"name": "p", "passed": True, "hidden": False},
        {"name": "h", "passed": False, "hidden": True},
    ]) is True
    # Honest failure (public also failing) is not gaming.
    assert gaming_suspected([
        {"name": "p", "passed": False, "hidden": False},
        {"name": "h", "passed": False, "hidden": True},
    ]) is False
    # No hidden checks -> can't judge.
    assert gaming_suspected([{"name": "p", "passed": True, "hidden": False}]) is False


def test_verdict_reveals_inputs_never_expected_values(tmp_path):
    from src.utils.oracle import verdict_for_agent
    results = run_checks(str(tmp_path), [
        {"name": "ok", "cmd": "echo fine", "expected_output": "fine"},
        {"name": "bad", "cmd": "cat", "stdin": "7 3", "expected_output": "TOP-SECRET-10"},
    ])
    verdict = verdict_for_agent(results)
    assert verdict["passed"] == 1 and verdict["failed"] == 1
    case = verdict["failing_cases"][0]
    assert case["name"] == "bad" and case["stdin"] == "7 3"
    assert "TOP-SECRET-10" not in str(verdict)


def test_stdin_reaches_the_command(tmp_path):
    results = run_checks(str(tmp_path), [
        {"name": "stdin", "cmd": "cat", "stdin": "piped-value", "expected_output": "piped-value"},
    ])
    assert results[0]["passed"] is True


def test_interface_plus_tests_synthesize_checks():
    from src.bench import _normalize_problems
    probs = _normalize_problems([{
        "id": "p",
        "prompt": "a calculator",
        "interface": "python3 main.py",
        "tests": [
            {"args": "add 2 3", "expected_output": "5"},
            {"args": "add 10 -3", "expected_output": "7", "hidden": True},
        ],
    }])
    p = probs[0]
    assert "invocable exactly as: `python3 main.py`" in p["prompt"]
    assert p["checks"][0]["cmd"] == "python3 main.py add 2 3"
    assert p["checks"][1]["hidden"] is True


def test_acceptance_tool_returns_verdict_only(tmp_path):
    from src.utils.tools import ToolHandler
    from src.utils.telemetry import TELEMETRY
    TELEMETRY.reset()
    handler = ToolHandler(
        project_root=str(tmp_path), agent_name="planner",
        acceptance_checks=[
            {"name": "pass", "cmd": "echo yes", "expected_output": "yes"},
            {"name": "fail", "cmd": "echo no", "expected_output": "HIDDEN-EXPECTED"},
        ],
    )
    verdict = handler.handle_function_call("run_acceptance_tests", {})
    assert verdict["passed"] == 1 and verdict["total"] == 2
    assert "HIDDEN-EXPECTED" not in str(verdict)
    assert TELEMETRY.counters["acceptance_tool_runs"] == 1


def test_examiner_mode_relaxes_runtime_verification(tmp_path):
    from src.utils.tools import ToolHandler
    handler = ToolHandler(project_root=str(tmp_path), agent_name="planner",
                          require_runtime_verification=False)
    handler.last_test_output = "===== 3 passed ====="
    result = handler.handle_function_call("mark_complete", {"reason": "tests pass"})
    assert result["success"] is True


def test_examiner_prompt_renders():
    from src.utils.prompt_manager import PromptManager
    rendered = PromptManager().render(
        "examiner_agent.j2",
        user_prompt="a fizzbuzz CLI",
        requirements_checklist='[{"id": "R1"}]',
        folder_structure="x/\nmain.py",
        has_acceptance_tests=True,
    )
    assert "independent examiner" in rendered
    assert "run_acceptance_tests" in rendered
    assert "APPROVE" in rendered and "REJECT" in rendered
