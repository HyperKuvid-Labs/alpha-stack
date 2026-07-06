"""Run telemetry — the research instrumentation layer.

Collects, per generation run: LLM usage (tokens, cached tokens, cost, latency)
attributed to the pipeline phase that spent them, pipeline-shape metrics
(refinement rounds, validator issues, file generation outcomes, planner
effort), phase wall-clock timings, and an automatic failure taxonomy.
Finalized into a single JSON report saved next to the project
(.alpha_stack/telemetry.json) and embedded in generate_project's result.

Pure stdlib; imported by everything, imports nothing from the package.
"""

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


class RunTelemetry:
    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with getattr(self, "_lock", threading.Lock()):
            self.run_id = uuid.uuid4().hex[:12]
            self.run_info: Dict[str, Any] = {}
            self.started_at = time.time()
            self._phase = "startup"
            self._phase_started = time.monotonic()
            self.phases: Dict[str, Dict[str, float]] = {}
            self.counters: Dict[str, int] = {}
            self.metrics: Dict[str, Any] = {}
            self.events: List[Dict[str, Any]] = []
            self.last_report: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    def start_run(self, prompt: str, provider: Optional[str], model: Optional[str],
                  output_dir: Optional[str] = None):
        self.reset()
        self.run_info = {
            "prompt": prompt,
            "provider": provider,
            "model": model,
            "output_dir": output_dir,
            "started_at_unix": self.started_at,
        }

    def set_phase(self, name: str):
        """Close the timing of the current phase and enter a new one."""
        now = time.monotonic()
        with self._lock:
            prev = self._phase
            elapsed = now - self._phase_started
            if prev:
                self.phases.setdefault(prev, self._empty_phase())
                self.phases[prev]["elapsed_s"] += round(elapsed, 3)
            self._phase = name
            self._phase_started = now
            self.phases.setdefault(name, self._empty_phase())

    @staticmethod
    def _empty_phase() -> Dict[str, float]:
        return {
            "llm_calls": 0, "llm_errors": 0,
            "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0,
            "cost_usd": 0.0, "llm_latency_s": 0.0, "elapsed_s": 0.0,
        }

    # ------------------------------------------------------------------
    # LLM usage recording
    # ------------------------------------------------------------------

    def record_llm_usage(self, prompt_tokens: int = 0, completion_tokens: int = 0,
                         cached_tokens: int = 0, cost_usd: Optional[float] = None,
                         latency_s: Optional[float] = None, error: bool = False,
                         phase: Optional[str] = None):
        with self._lock:
            name = phase or self._phase
            p = self.phases.setdefault(name, self._empty_phase())
            p["llm_calls"] += 1
            if error:
                p["llm_errors"] += 1
            p["prompt_tokens"] += int(prompt_tokens or 0)
            p["completion_tokens"] += int(completion_tokens or 0)
            p["cached_tokens"] += int(cached_tokens or 0)
            if cost_usd:
                p["cost_usd"] = round(p["cost_usd"] + float(cost_usd), 6)
            if latency_s:
                p["llm_latency_s"] = round(p["llm_latency_s"] + latency_s, 3)

    def record_openai_response(self, response: Any, latency_s: Optional[float] = None):
        """Extract usage from an OpenAI-compatible completion (incl. OpenRouter
        usage accounting: cached tokens and actual cost when requested)."""
        try:
            usage = getattr(response, "usage", None)
            if usage is None:
                return
            cached = 0
            details = getattr(usage, "prompt_tokens_details", None)
            if details is not None:
                cached = getattr(details, "cached_tokens", 0) or 0
            self.record_llm_usage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                cached_tokens=cached,
                cost_usd=getattr(usage, "cost", None),
                latency_s=latency_s,
            )
        except Exception:
            pass

    def record_google_response(self, response: Any, latency_s: Optional[float] = None):
        try:
            meta = getattr(response, "usage_metadata", None)
            if meta is None:
                return
            self.record_llm_usage(
                prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                cached_tokens=getattr(meta, "cached_content_token_count", 0) or 0,
                latency_s=latency_s,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Pipeline metrics
    # ------------------------------------------------------------------

    def incr(self, name: str, n: int = 1):
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + n

    def set_metric(self, key: str, value: Any):
        with self._lock:
            self.metrics[key] = value

    def append_metric(self, key: str, value: Any):
        with self._lock:
            self.metrics.setdefault(key, []).append(value)

    def add_event(self, kind: str, detail: str = ""):
        with self._lock:
            if len(self.events) < 500:
                self.events.append({
                    "t": round(time.time() - self.started_at, 2),
                    "phase": self._phase,
                    "kind": kind,
                    "detail": str(detail)[:300],
                })

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    def _classify_failure(self, success: bool) -> str:
        if success:
            return "success"
        stage = self.metrics.get("failure_stage")
        if stage:
            return str(stage)
        if self.counters.get("planner_gave_up"):
            return "planner_gave_up"
        if self.counters.get("planner_stalled"):
            return "planner_stalled"
        if "fix_loop" in self.phases and self.phases["fix_loop"]["llm_calls"] > 0:
            return "tests_never_passed"
        if self.metrics.get("files_failed", 0):
            return "file_generation_failed"
        return "unknown"

    def finalize(self, success: bool) -> Dict[str, Any]:
        self.set_phase("end")  # close the last real phase's timing
        with self._lock:
            totals = self._empty_phase()
            for p in self.phases.values():
                for k in totals:
                    if k != "elapsed_s":
                        totals[k] += p[k]
            totals["elapsed_s"] = round(time.time() - self.started_at, 2)
            totals["total_tokens"] = totals["prompt_tokens"] + totals["completion_tokens"]
            report = {
                "run_id": self.run_id,
                "run": dict(self.run_info),
                "success": bool(success),
                "outcome": self._classify_failure(success),
                "totals": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in totals.items()},
                "phases": {k: dict(v) for k, v in self.phases.items() if v["llm_calls"] or v["elapsed_s"] > 0.05},
                "counters": dict(self.counters),
                "metrics": dict(self.metrics),
                "events": list(self.events),
            }
            self.last_report = report
            return report

    def save(self, directory: str) -> Optional[str]:
        """Write the finalized report to <directory>/telemetry.json."""
        if self.last_report is None:
            return None
        try:
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, "telemetry.json")
            with open(path, "w") as f:
                json.dump(self.last_report, f, indent=2, default=str)
            return path
        except Exception:
            return None

    def summary_line(self) -> str:
        r = self.last_report
        if not r:
            return ""
        t = r["totals"]
        cost = f" · ${t['cost_usd']:.4f}" if t.get("cost_usd") else ""
        cached = f" ({t['cached_tokens']} cached)" if t.get("cached_tokens") else ""
        return (
            f"[telemetry] {r['outcome']} · {t['llm_calls']} LLM calls · "
            f"{t['total_tokens']} tokens{cached}{cost} · {t['elapsed_s']}s"
        )


TELEMETRY = RunTelemetry()
