"""Telemetry collection and bench harness — the research instrumentation."""

import json

from src.bench import load_problems, run_bench
from src.utils.telemetry import RunTelemetry, TELEMETRY


class _Usage:
    prompt_tokens = 100
    completion_tokens = 40
    cost = 0.0012

    class prompt_tokens_details:
        cached_tokens = 60


class _Resp:
    usage = _Usage()


def test_phase_attribution_and_totals():
    t = RunTelemetry()
    t.start_run("p", "openrouter", "m")
    t.set_phase("architecture")
    t.record_openai_response(_Resp(), latency_s=1.2)
    t.set_phase("blueprint")
    t.record_openai_response(_Resp())
    t.record_llm_usage(error=True)
    report = t.finalize(True)

    assert report["outcome"] == "success"
    arch, bp = report["phases"]["architecture"], report["phases"]["blueprint"]
    assert arch["llm_calls"] == 1 and arch["prompt_tokens"] == 100
    assert arch["cached_tokens"] == 60 and arch["cost_usd"] == 0.0012
    assert bp["llm_calls"] == 2 and bp["llm_errors"] == 1
    totals = report["totals"]
    assert totals["total_tokens"] == 280  # 2 successful calls x 140
    assert totals["llm_calls"] == 3


def test_failure_taxonomy():
    t = RunTelemetry()
    t.start_run("p", "openrouter", "m")
    t.set_metric("failure_stage", "blueprint_failed")
    assert t.finalize(False)["outcome"] == "blueprint_failed"

    t = RunTelemetry()
    t.start_run("p", "openrouter", "m")
    t.incr("planner_gave_up")
    assert t.finalize(False)["outcome"] == "planner_gave_up"

    t = RunTelemetry()
    t.start_run("p", "openrouter", "m")
    t.set_phase("fix_loop")
    t.record_openai_response(_Resp())
    assert t.finalize(False)["outcome"] == "tests_never_passed"


def test_load_problems_jsonl_and_array(tmp_path):
    jl = tmp_path / "p.jsonl"
    jl.write_text('{"id": "a", "prompt": "build a"}\n{"prompt": "build b"}\n')
    probs = load_problems(str(jl))
    assert [p["id"] for p in probs] == ["a", "problem_02"]

    arr = tmp_path / "p.json"
    arr.write_text(json.dumps([{"id": "x", "prompt": "build x"}]))
    assert load_problems(str(arr))[0]["id"] == "x"


def test_run_bench_isolates_and_aggregates(tmp_path, monkeypatch):
    problems = tmp_path / "problems.jsonl"
    problems.write_text(
        '{"id": "ok_one", "prompt": "works"}\n'
        '{"id": "bad_one", "prompt": "crashes"}\n'
    )

    def fake_generate(prompt, out_dir, on_status=None, provider_name=None, model_override=None):
        TELEMETRY.start_run(prompt, provider_name, model_override, out_dir)
        TELEMETRY.set_phase("architecture")
        TELEMETRY.record_llm_usage(prompt_tokens=10, completion_tokens=5)
        if prompt == "crashes":
            TELEMETRY.finalize(False)
            raise RuntimeError("boom")
        TELEMETRY.set_metric("planned_files", 3)
        TELEMETRY.finalize(True)
        return {"success": True, "project_path": out_dir, "elapsed_time": 1.0}

    import src.bench as bench_mod
    monkeypatch.setattr("src.generator.generate_project", fake_generate)

    summary = run_bench(str(problems), str(tmp_path / "results"), model="test-model")
    assert summary["n_problems"] == 2
    assert summary["n_success"] == 1

    rows = {r["problem_id"]: r for r in summary["rows"]}
    assert rows["ok_one"]["success"] is True
    assert rows["ok_one"]["total_tokens"] == 15
    assert rows["ok_one"]["planned_files"] == 3
    assert rows["bad_one"]["success"] is False
    assert "harness_error" in rows["bad_one"]["outcome"]

    run_dir = next((tmp_path / "results").iterdir())
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "summary.csv").exists()
    per_problem = json.load(open(run_dir / "ok_one" / "bench_result.json"))
    assert per_problem["telemetry"]["totals"]["total_tokens"] == 15


def test_trial_cycle_reconstruction(tmp_path):
    """Planner edits between shell runs are grouped into trials:
    run -> fail -> N edits -> run again, each boundary recorded."""
    from src.utils.tools import ToolHandler

    TELEMETRY.reset()
    handler = ToolHandler(project_root=str(tmp_path), agent_name="planner")

    (tmp_path / "a.py").write_text("x = 1\n")
    handler.handle_function_call(
        "update_file_code",
        {"file_path": "a.py", "new_content": "x = 2\n", "change_description": "fix"},
    )
    handler.handle_function_call(
        "update_file_code",
        {"file_path": "a.py", "new_content": "x = 3\n", "change_description": "fix again"},
    )
    handler.handle_function_call("run_shell_command", {"command": "echo trial-one"})
    handler.handle_function_call("run_shell_command", {"command": "echo trial-two"})
    handler.cleanup()

    trials = TELEMETRY.metrics["trials"]
    assert len(trials) == 2
    assert trials[0]["edits_since_last_run"] == 2
    assert trials[1]["edits_since_last_run"] == 0
    assert TELEMETRY.counters["total_edits"] == 2
    assert TELEMETRY.counters["planner_tool_calls"] == 4
    assert TELEMETRY.counters["tool_run_shell_command"] == 2


def test_load_problems_txt_directory(tmp_path):
    d = tmp_path / "problems"
    d.mkdir()
    (d / "one.txt").write_text("build one")
    (d / "two.txt").write_text("build two")
    probs = load_problems(str(d))
    assert [p["id"] for p in probs] == ["one", "two"]
    assert probs[0]["prompt"] == "build one"
