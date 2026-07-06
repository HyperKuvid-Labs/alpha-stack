"""Batch evaluation runner — the research harness.

Takes a problems file (JSONL: one {"id": ..., "prompt": ...} per line, or a
JSON array), runs the full generation pipeline on each problem in an isolated
output directory, and collects per-problem telemetry plus an aggregate
summary (JSON + CSV) ready for analysis/plotting.

Each problem is fully isolated: telemetry is reset between runs and one
problem's crash never stops the batch.
"""

import contextlib
import csv
import json
import os
import subprocess
import time
import traceback
from typing import Any, Dict, List, Optional

from .utils.oracle import gaming_suspected, run_checks
from .utils.telemetry import TELEMETRY

SUMMARY_COLUMNS = [
    "problem_id", "success", "outcome", "elapsed_s",
    "llm_calls", "total_tokens", "prompt_tokens", "completion_tokens",
    "cached_tokens", "cost_usd",
    "checklist_items", "planned_files", "files_generated", "files_failed",
    "blueprint_mode", "structural_issue_rounds",
    "planner_rounds", "planner_tool_calls", "total_edits", "test_runs",
    "rounds_to_green", "orchestrator_escalations", "file_retry_rounds",
    "oracle_public", "oracle_hidden", "oracle_gaming_suspected",
    "project_path",
]


def load_problems(path: str) -> List[Dict[str, Any]]:
    """Parse problems from JSONL ({"id", "prompt"} per line), a JSON array,
    a directory of .txt files (one problem per file, id = filename stem), or
    a single .txt file (the whole file is one prompt)."""
    if os.path.isdir(path):
        items: List[Any] = []
        for name in sorted(os.listdir(path)):
            if name.endswith(".txt"):
                with open(os.path.join(path, name)) as f:
                    prompt = f.read().strip()
                if prompt:
                    items.append({"id": os.path.splitext(name)[0], "prompt": prompt})
        if not items:
            raise ValueError(f"No non-empty .txt problems in directory: {path}")
        return _normalize_problems(items)

    with open(path, "r") as f:
        text = f.read().strip()
    if not text:
        raise ValueError(f"Problems file is empty: {path}")

    if path.endswith(".txt"):
        items = [{"id": os.path.splitext(os.path.basename(path))[0], "prompt": text}]
    elif text.startswith("["):
        items = json.loads(text)
    else:
        items = [json.loads(line) for line in text.splitlines() if line.strip()]

    return _normalize_problems(items)


def _normalize_problems(items: List[Any]) -> List[Dict[str, Any]]:
    problems = []
    for i, item in enumerate(items, 1):
        if isinstance(item, str):
            item = {"prompt": item}
        if not isinstance(item, dict) or not item.get("prompt"):
            raise ValueError(f"Problem #{i} has no 'prompt' field: {item!r}")
        item.setdefault("id", f"problem_{i:02d}")
        problems.append(item)
    return problems


def _git_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ).stdout.strip()
    except Exception:
        return ""


def _summary_row(problem_id: str, result: Optional[Dict], report: Optional[Dict],
                 error: Optional[str] = None) -> Dict[str, Any]:
    row: Dict[str, Any] = {c: "" for c in SUMMARY_COLUMNS}
    row["problem_id"] = problem_id
    row["success"] = bool(result and result.get("success"))
    if report:
        totals = report.get("totals", {})
        metrics = report.get("metrics", {})
        counters = report.get("counters", {})
        row.update({
            "outcome": report.get("outcome", ""),
            "elapsed_s": totals.get("elapsed_s", ""),
            "llm_calls": totals.get("llm_calls", ""),
            "total_tokens": totals.get("total_tokens", ""),
            "prompt_tokens": totals.get("prompt_tokens", ""),
            "completion_tokens": totals.get("completion_tokens", ""),
            "cached_tokens": totals.get("cached_tokens", ""),
            "cost_usd": totals.get("cost_usd", ""),
            "checklist_items": metrics.get("checklist_items", ""),
            "planned_files": metrics.get("planned_files", ""),
            "files_generated": metrics.get("files_generated", ""),
            "files_failed": metrics.get("files_failed", ""),
            "blueprint_mode": metrics.get("blueprint_mode", ""),
            "structural_issue_rounds": len(metrics.get("structural_issues_per_round", []) or []),
            "planner_rounds": counters.get("planner_rounds", ""),
            "planner_tool_calls": counters.get("planner_tool_calls", ""),
            "total_edits": counters.get("total_edits", ""),
            "test_runs": len(metrics.get("trials", []) or []),
            "rounds_to_green": metrics.get("rounds_to_green", ""),
            "orchestrator_escalations": counters.get("orchestrator_escalations", ""),
            "file_retry_rounds": counters.get("file_retry_rounds", ""),
            "oracle_public": metrics.get("oracle_public", ""),
            "oracle_hidden": metrics.get("oracle_hidden", ""),
            "oracle_gaming_suspected": metrics.get("oracle_gaming_suspected", ""),
        })
    if error:
        row["outcome"] = f"harness_error: {error[:120]}"
    if result:
        row["project_path"] = result.get("project_path", "")
    return row


def run_bench(problems_path: str, output_root: str,
              provider_name: Optional[str] = None,
              model: Optional[str] = None,
              limit: Optional[int] = None,
              on_status=None) -> Dict[str, Any]:
    from .generator import generate_project

    problems = load_problems(problems_path)
    if limit:
        problems = problems[:limit]

    run_id = time.strftime("run_%Y%m%d_%H%M%S")
    run_dir = os.path.join(output_root, run_id)
    os.makedirs(run_dir, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    print(f"[bench] {len(problems)} problem(s) → {run_dir}"
          + (f" · model={model}" if model else ""))

    for idx, problem in enumerate(problems, 1):
        pid = str(problem["id"])
        problem_dir = os.path.join(run_dir, pid)
        os.makedirs(problem_dir, exist_ok=True)
        print(f"\n[bench] ({idx}/{len(problems)}) {pid}: {problem['prompt'][:80]}...")

        # Reproducibility manifest — the exact inputs this run received.
        with open(os.path.join(problem_dir, "run_config.json"), "w") as f:
            json.dump({
                "problem": problem,
                "provider": provider_name,
                "model": model,
                "alphastack_revision": _git_revision(),
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, f, indent=2)

        checks = problem.get("checks") or []
        public_checks = [c for c in checks if not c.get("hidden")]

        TELEMETRY.reset()
        result, report, error = None, None, None
        started = time.time()
        log_path = os.path.join(problem_dir, "run.log")
        with open(log_path, "w") as log_file:
            def log_status(event_type, message, **kwargs):
                log_file.write(f"[{event_type}] {message}\n")
                log_file.flush()
                if on_status:
                    on_status(event_type, message, **kwargs)

            try:
                with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
                    result = generate_project(
                        problem["prompt"],
                        problem_dir,
                        on_status=log_status,
                        provider_name=provider_name,
                        model_override=model,
                        oracle_checks=public_checks,
                    )
                report = TELEMETRY.last_report
            except Exception as exc:
                error = str(exc)
                report = TELEMETRY.last_report
                print(f"[bench] {pid} crashed the harness: {exc}")
                traceback.print_exc(file=log_file)

        # Grade against the full oracle — including checks the pipeline never
        # saw. Public-pass + hidden-fail is the signature of hardcoded answers.
        oracle_results = []
        if checks and result and result.get("project_path"):
            oracle_results = run_checks(result["project_path"], checks)
            public = [r for r in oracle_results if not r.get("hidden")]
            hidden = [r for r in oracle_results if r.get("hidden")]
            gaming = gaming_suspected(oracle_results)
            if report is not None:
                m = report.setdefault("metrics", {})
                m["oracle_public"] = f"{sum(r['passed'] for r in public)}/{len(public)}"
                m["oracle_hidden"] = f"{sum(r['passed'] for r in hidden)}/{len(hidden)}"
                m["oracle_gaming_suspected"] = gaming
            print(f"[bench] {pid} oracle: public "
                  f"{sum(r['passed'] for r in public)}/{len(public)}, hidden "
                  f"{sum(r['passed'] for r in hidden)}/{len(hidden)}"
                  + (" · GAMING SUSPECTED" if gaming else ""))

        # Per-problem artifact: everything needed to analyze this run alone.
        with open(os.path.join(problem_dir, "bench_result.json"), "w") as f:
            json.dump({
                "problem": problem,
                "harness_elapsed_s": round(time.time() - started, 2),
                "result": result,
                "telemetry": report,
                "oracle_results": oracle_results,
                "harness_error": error,
            }, f, indent=2, default=str)

        row = _summary_row(pid, result, report, error)
        rows.append(row)
        print(f"[bench] {pid} → {row['outcome'] or ('success' if row['success'] else 'failed')} "
              f"· {row['total_tokens'] or '?'} tokens · {row['elapsed_s'] or '?'}s")

    summary = {
        "run_id": run_id,
        "problems_file": os.path.abspath(problems_path),
        "provider": provider_name,
        "model": model,
        "n_problems": len(rows),
        "n_success": sum(1 for r in rows if r["success"]),
        "rows": rows,
    }
    with open(os.path.join(run_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    with open(os.path.join(run_dir, "summary.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[bench] done: {summary['n_success']}/{summary['n_problems']} succeeded")
    print(f"[bench] summary: {os.path.join(run_dir, 'summary.json')} (+ summary.csv)")
    return summary
