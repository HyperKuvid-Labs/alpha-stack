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
