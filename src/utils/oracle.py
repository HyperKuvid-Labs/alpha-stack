"""External acceptance checks (oracle) for generated projects.

A check runs a shell command inside the generated project and compares the
observable outcome against author-supplied expectations. Checks are written
by the problem author, never by the pipeline, so they cannot inherit the
pipeline's blind spots.

Check schema (per problem, optional):
    {"name": "median_even",
     "cmd": ".venv/bin/python main.py data/fixture.txt",
     "expected_output": "median: 4.5000",     # substring of stdout+stderr
     "expected_exit": 0,                       # optional, exact match
     "hidden": true}                           # never revealed to the agent

Public checks (hidden=false, the default) may be shown to the fix loop when
they fail. Hidden checks run only in the bench harness after the run ends;
a run whose public checks pass while hidden siblings fail is flagged as
suspected oracle gaming (hardcoded answers).
"""

import subprocess
from typing import Any, Dict, List

CHECK_TIMEOUT_S = 120


def run_checks(project_dir: str, checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Execute checks in project_dir. Returns one result dict per check."""
    results = []
    for check in checks or []:
        cmd = str(check.get("cmd", "")).strip()
        name = check.get("name") or cmd[:40]
        expected_output = check.get("expected_output")
        expected_exit = check.get("expected_exit")
        if not cmd or (expected_output is None and expected_exit is None):
            results.append({"name": name, "cmd": cmd, "passed": False,
                            "error": "check needs cmd and expected_output and/or expected_exit"})
            continue
        try:
            proc = subprocess.run(
                cmd, shell=True, cwd=project_dir,
                capture_output=True, text=True, timeout=CHECK_TIMEOUT_S,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            exit_ok = expected_exit is None or proc.returncode == expected_exit
            output_ok = expected_output is None or str(expected_output) in output
            results.append({
                "name": name,
                "cmd": cmd,
                "hidden": bool(check.get("hidden")),
                "passed": exit_ok and output_ok,
                "exit_code": proc.returncode,
                "expected_output": expected_output,
                "expected_exit": expected_exit,
                "output_tail": output[-400:],
            })
        except subprocess.TimeoutExpired:
            results.append({"name": name, "cmd": cmd, "hidden": bool(check.get("hidden")),
                            "passed": False, "error": f"timed out after {CHECK_TIMEOUT_S}s"})
        except Exception as exc:
            results.append({"name": name, "cmd": cmd, "hidden": bool(check.get("hidden")),
                            "passed": False, "error": str(exc)})
    return results


def format_failures_for_agent(results: List[Dict[str, Any]]) -> str:
    """Human/agent-readable report of FAILED public checks only. Hidden
    checks are never formatted — they must stay invisible to the pipeline."""
    lines = []
    for r in results:
        if r.get("passed") or r.get("hidden"):
            continue
        lines.append(f"- CHECK FAILED: {r['name']}")
        lines.append(f"    command: {r['cmd']}")
        if r.get("error"):
            lines.append(f"    error: {r['error']}")
            continue
        if r.get("expected_exit") is not None:
            lines.append(f"    expected exit code {r['expected_exit']}, got {r.get('exit_code')}")
        if r.get("expected_output") is not None:
            lines.append(f"    expected output to contain: {r['expected_output']!r}")
            lines.append(f"    actual output (tail): {r.get('output_tail', '')[-300:]!r}")
    return "\n".join(lines)


def gaming_suspected(results: List[Dict[str, Any]]) -> bool:
    """Public checks all pass while at least one hidden check fails —
    the signature of hardcoded answers."""
    public = [r for r in results if not r.get("hidden")]
    hidden = [r for r in results if r.get("hidden")]
    if not public or not hidden:
        return False
    return all(r.get("passed") for r in public) and any(not r.get("passed") for r in hidden)
