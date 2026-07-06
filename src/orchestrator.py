import os
import logging
import uuid
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Condition, Lock, Event as ThreadEvent, Thread
from queue import Queue, Empty
import time

from .utils.agent_memory import AgentMemory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress noisy HTTP request logs from OpenAI/httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


class FileTracker:
    """
    Shared completion state. Agents call wait_for_file() inside their tool loop
    to block until a specific file is ready, then read it themselves.
    Condition.notify_all() wakes waiters immediately — no polling.
    """

    def __init__(self):
        self._condition = Condition(Lock())
        self._done: set = set()
        self._failed: set = set()
        # waiter filepath -> filepath it is blocked on (for cycle detection)
        self._waiting_on: Dict[str, str] = {}

    def mark_done(self, filepath: str):
        with self._condition:
            self._done.add(filepath)
            logger.info(f"[Tracker] Done: {filepath}")
            self._condition.notify_all()

    def mark_failed(self, filepath: str):
        with self._condition:
            self._failed.add(filepath)
            logger.warning(f"[Tracker] Failed: {filepath}")
            self._condition.notify_all()

    def _creates_cycle(self, waiter: str, target: str) -> bool:
        """Follow the waiting chain from target; a path back to waiter is a cycle.
        Caller must hold self._condition."""
        seen = set()
        current = target
        while current is not None and current not in seen:
            if current == waiter:
                return True
            seen.add(current)
            current = self._waiting_on.get(current)
        return False

    def wait_for_file(self, filepath: str, waiter: Optional[str] = None,
                      timeout: Optional[float] = None) -> str:
        """Block until `filepath` is done or failed.

        Returns "done", "failed", "timeout", or "deadlock".

        Workers run inside a bounded ThreadPoolExecutor, so an unbounded wait
        can starve the pool: every running worker blocks on a file whose worker
        is still queued, and nothing ever runs. Two guards prevent that:
        - `waiter` (the filepath of the worker doing the waiting) registers the
          wait edge; if the new edge closes a cycle (A waits on B, B waits on A)
          the closer gets "deadlock" back immediately.
        - `timeout` bounds the wait for the non-cyclic starvation case.
        Callers treat "timeout"/"deadlock" as "proceed without the file's code".
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            if waiter is not None:
                if self._creates_cycle(waiter, filepath):
                    logger.warning(f"[Tracker] Wait cycle: {waiter} -> {filepath} — breaking")
                    return "deadlock"
                self._waiting_on[waiter] = filepath
            try:
                while filepath not in self._done and filepath not in self._failed:
                    remaining = None if deadline is None else deadline - time.monotonic()
                    if remaining is not None and remaining <= 0:
                        logger.warning(f"[Tracker] Wait timed out: {waiter or '?'} -> {filepath}")
                        return "timeout"
                    self._condition.wait(timeout=remaining)
                return "done" if filepath in self._done else "failed"
            finally:
                if waiter is not None:
                    self._waiting_on.pop(waiter, None)

    def reset_file(self, filepath: str):
        """Remove a file from the failed set so it can be retried."""
        with self._condition:
            self._failed.discard(filepath)

    def list_done(self) -> List[str]:
        with self._condition:
            return list(self._done)

    def list_failed(self) -> List[str]:
        with self._condition:
            return list(self._failed)

    def summary(self) -> str:
        with self._condition:
            return f"done={len(self._done)}, failed={len(self._failed)}"


class DependencyRegistry:
    """
    Continuously updated registry of external package imports per file.
    Updated immediately after each file is written.
    Agents query all_external_packages() via the get_external_packages tool.
    """

    def __init__(self):
        self._lock = Lock()
        self._external: Dict[str, List[str]] = {}

    def register(self, filepath: str, dep_details: List[Dict]):
        external = sorted({
            d["raw"] for d in dep_details
            if d.get("kind") == "external" and d.get("raw")
        })
        with self._lock:
            self._external[filepath] = external

    def all_external_packages(self) -> List[str]:
        with self._lock:
            seen: set = set()
            result = []
            for pkgs in self._external.values():
                for p in pkgs:
                    if p not in seen:
                        seen.add(p)
                        result.append(p)
            return sorted(result)


class OrchestratorMailbox:
    """
    Thread-safe mailbox for child agents to ask the orchestrator questions.
    Queries from concurrent children are batched so the orchestrator sees
    the bigger picture and can give coordinated responses.
    """

    def __init__(self):
        self._inbox: Queue = Queue()
        self._events: Dict[str, ThreadEvent] = {}
        self._results: Dict[str, str] = {}
        self._history: List[Dict] = []
        self._lock = Lock()

    def ask(self, question: str, filepath: str) -> str:
        """Submit a query and block until the orchestrator responds."""
        from .utils.telemetry import TELEMETRY
        TELEMETRY.incr("orchestrator_escalations")
        query_id = str(uuid.uuid4())[:8]
        event = ThreadEvent()
        with self._lock:
            self._events[query_id] = event

        self._inbox.put({
            "id": query_id,
            "filepath": filepath,
            "question": question,
        })

        event.wait(timeout=180)  # Max 3 min

        with self._lock:
            self._events.pop(query_id, None)
            return self._results.pop(query_id, "Orchestrator timed out.")

    def drain(self, timeout: float = 5.0) -> List[Dict]:
        """Block until at least one query arrives, then grab any others already queued."""
        queries = []

        # Wait for first query
        try:
            queries.append(self._inbox.get(timeout=timeout))
        except Empty:
            return []

        # Grab any other queries already in the queue (no waiting)
        while not self._inbox.empty():
            try:
                queries.append(self._inbox.get_nowait())
            except Empty:
                break

        return queries

    def respond(self, query_id: str, response: str):
        """Route response back to the waiting child agent."""
        with self._lock:
            self._results[query_id] = response
            event = self._events.get(query_id)
            if event:
                event.set()

    def add_to_history(self, queries: List[Dict], responses: Dict[str, str]):
        """Record processed Q&As for context in future batches."""
        with self._lock:
            for q in queries:
                resp = responses.get(q["id"], "")
                self._history.append({
                    "filepath": q["filepath"],
                    "question": q["question"][:300],
                    "response": resp[:500],
                })
            # Keep last 15 Q&As
            self._history = self._history[-15:]

    def get_history(self) -> List[Dict]:
        with self._lock:
            return list(self._history)


class ParallelOrchestrator:
    """
    All file-generation agents are spawned immediately in parallel.
    Each child agent runs an agentic loop with 4 tools:
      - read_file(filepath)         → waits for the file, returns its content
      - get_external_packages()     → returns all third-party packages found so far
      - list_generated_files()      → returns all files generated so far
      - ask_orchestrator(question)  → queued to orchestrator via mailbox (batched)

    The orchestrator runs in a dedicated thread, processing batched queries
    from children with full blueprint context and action tools.
    On child failure, the worker escalates via the same mailbox.
    """

    def __init__(self, output_base_dir: str, max_workers: int = 20):
        self.output_base_dir = output_base_dir
        self.max_workers = max_workers
        self.tracker = FileTracker()
        self._gen_log = None  # Initialized in execute()
        self.dep_registry = DependencyRegistry()
        self.mailbox = OrchestratorMailbox()
        self.memory = AgentMemory(project_root=output_base_dir, role="orchestrator")
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self.blueprint_context: Optional[Dict[str, Any]] = None
        self._shutdown = ThreadEvent()

    def set_blueprint(self, software_blueprint: Dict, folder_structure: str, file_formats: Dict):
        """Store the full blueprint for the orchestrator agent."""
        self.blueprint_context = {
            "software_blueprint": software_blueprint,
            "folder_structure": folder_structure,
            "file_formats": file_formats,
        }

    def add_node(self, filepath: str, prompt_rules: str):
        normalized = os.path.normpath(filepath)
        self._tasks[normalized] = {"prompt_rules": prompt_rules}
        logger.info(f"[Orchestrator] Registered: {normalized}")

    # ------------------------------------------------------------------
    # Per-file worker
    # ------------------------------------------------------------------

    def _worker(self, filepath: str):
        from .generator import generate_file
        from .utils.prompt_manager import PromptManager

        full_path = os.path.join(self.output_base_dir, filepath)

        # Checkpointing
        if os.path.exists(full_path):
            logger.info(f"[Orchestrator] Checkpoint hit — skipping: {filepath}")
            self._register_deps(filepath, full_path)
            self.tracker.mark_done(filepath)
            return

        pm = PromptManager()
        prompt_rules = self._tasks[filepath]["prompt_rules"]
        reg_files = set(self._tasks.keys())

        # --- Child agent attempts (no fixed limit — retry until success or consecutive failures) ---
        max_consecutive_failures = 5
        result = None
        attempt = 0
        consecutive_failures = 0
        while consecutive_failures < max_consecutive_failures:
            attempt += 1
            try:
                result = generate_file(
                    filepath=filepath,
                    prompt_rules=prompt_rules,
                    pm=pm,
                    tracker=self.tracker,
                    dep_registry=self.dep_registry,
                    output_base_dir=self.output_base_dir,
                    registered_files=reg_files,
                    blueprint_context=self.blueprint_context,
                    orchestrator_mailbox=self.mailbox,
                    gen_log=self._gen_log,
                )
                if result and result.file_content:
                    break
                result = None
                consecutive_failures += 1
            except Exception as e:
                logger.warning(f"[Orchestrator] Attempt {attempt} failed for {filepath}: {e}")
                consecutive_failures += 1
            if consecutive_failures < max_consecutive_failures:
                time.sleep(min(2 ** attempt, 16))

        # --- Escalation: if child failed, ask orchestrator via mailbox ---
        if (result is None or not result.file_content) and self.blueprint_context:
            logger.info(f"[Orchestrator] Child failed for {filepath} — escalating via mailbox")
            guidance = self.mailbox.ask(
                question=(
                    f"ESCALATION: The child agent failed to generate '{filepath}' after multiple attempts. "
                    f"Purpose: {prompt_rules}. "
                    f"Please provide specific guidance for generating this file — "
                    f"exact imports, class/function signatures, how it connects to other files. "
                    f"You can also use regenerate_file to generate it directly."
                ),
                filepath=filepath,
            )

            # Check if orchestrator already regenerated the file directly
            if os.path.exists(full_path) and filepath in self.tracker.list_done():
                logger.info(f"[Orchestrator] Orchestrator already regenerated {filepath} — skipping retry")
                return

            # Retry child with orchestrator guidance
            try:
                result = generate_file(
                    filepath=filepath,
                    prompt_rules=prompt_rules + "\n\nOrchestrator guidance:\n" + guidance,
                    pm=pm,
                    tracker=self.tracker,
                    dep_registry=self.dep_registry,
                    output_base_dir=self.output_base_dir,
                    registered_files=reg_files,
                    blueprint_context=self.blueprint_context,
                    orchestrator_mailbox=self.mailbox,
                    gen_log=self._gen_log,
                )
            except Exception as e:
                logger.error(f"[Orchestrator] Escalation retry failed for {filepath}: {e}")
                result = None

        # --- Write result or mark failed ---
        if result and result.file_content:
            os.makedirs(os.path.dirname(full_path) or self.output_base_dir, exist_ok=True)
            with open(full_path, "w") as f:
                f.write(result.file_content)
            self._register_deps(filepath, full_path, content=result.file_content)
            self.tracker.mark_done(filepath)
            logger.info(f"[Orchestrator] Generated: {filepath}")
        else:
            self.tracker.mark_failed(filepath)
            logger.error(f"[Orchestrator] Failed to generate: {filepath}")

    def _register_deps(self, filepath: str, full_path: str, content: Optional[str] = None):
        """Extract external imports from a just-written file and update DependencyRegistry."""
        try:
            from .utils.treesitter_parser import parse_file
            pr = parse_file(full_path)
            details: List[Dict] = []
            if pr is not None:
                for imp in getattr(pr, "imports", []) or []:
                    module = (imp.module or imp.raw or "").strip()
                    if not module or module.startswith("."):
                        continue
                    details.append({"raw": module, "kind": "external", "path": None})
            self.dep_registry.register(filepath, details)
        except Exception as e:
            logger.warning(f"[Orchestrator] Dep extraction failed for {filepath}: {e}")

    # ------------------------------------------------------------------
    # Orchestrator thread — processes batched queries from children
    # ------------------------------------------------------------------

    def _orchestrator_thread(self):
        from .generator import process_orchestrator_batch
        from .utils.prompt_manager import PromptManager

        pm = PromptManager()

        while not self._shutdown.is_set():
            queries = self.mailbox.drain(timeout=5.0)
            if not queries:
                continue

            logger.info(f"[Orchestrator] Processing batch of {len(queries)} queries")

            if not self.blueprint_context:
                for q in queries:
                    self.mailbox.respond(q["id"], "No blueprint context available.")
                continue

            responses = process_orchestrator_batch(
                queries=queries,
                blueprint_context=self.blueprint_context,
                tracker=self.tracker,
                dep_registry=self.dep_registry,
                output_base_dir=self.output_base_dir,
                registered_files=set(self._tasks.keys()),
                orchestrator_ref=self,
                pm=pm,
                history=self.mailbox.get_history(),
                memory=self.memory,
            )

            for q in queries:
                self.mailbox.respond(q["id"], responses.get(q["id"], "No response generated."))

            self.mailbox.add_to_history(queries, responses)

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _dependency_order(self) -> List[str]:
        """Order files so likely dependencies get worker threads first.

        Heuristic: a file whose basename stem appears in many other files'
        contracts (e.g. utils, models, config) is likely read by their workers,
        so it should generate early. Ties keep tests after source via path sort.
        """
        paths = list(self._tasks)

        def ref_count(path: str) -> int:
            stem = os.path.splitext(os.path.basename(path))[0]
            if len(stem) < 3:
                return 0
            return sum(
                1 for other in paths
                if other != path and stem in self._tasks[other]["prompt_rules"]
            )

        return sorted(paths, key=lambda p: (-ref_count(p), "test" in p.lower(), p))

    def _run_workers(self, filepaths):
        """Spawn workers for the given filepaths in parallel."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._worker, fp): fp for fp in filepaths}
            for future in as_completed(futures):
                fp = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"[Orchestrator] Unhandled exception for {fp}: {e}")
                    self.tracker.mark_failed(fp)

    def execute(self):
        from .generator import GenerationLog
        self._gen_log = GenerationLog(self.output_base_dir)

        print(f"[Orchestrator] Spawning {len(self._tasks)} agents in parallel...", flush=True)

        # Start the orchestrator thread
        self._shutdown.clear()
        orch_thread = Thread(target=self._orchestrator_thread, daemon=True)
        orch_thread.start()

        # --- First pass: all files, dependencies scheduled first ---
        self._run_workers(self._dependency_order())

        # --- Retry failed files until all succeed or no progress is made ---
        retry_round = 0
        while True:
            failed = self.tracker.list_failed()
            if not failed:
                break

            retry_round += 1
            from .utils.telemetry import TELEMETRY
            TELEMETRY.incr("file_retry_rounds")
            num_failed = len(failed)
            print(f"[Orchestrator] Retry round {retry_round}: {num_failed} failed files", flush=True)

            for fp in failed:
                self.tracker.reset_file(fp)

            self._run_workers(failed)

            # Stop if no progress — same files still failing
            still_failed = self.tracker.list_failed()
            if len(still_failed) >= num_failed:
                logger.warning(f"[Orchestrator] No progress in retry round {retry_round} — stopping retries")
                break

        # Shutdown orchestrator thread
        self._shutdown.set()
        orch_thread.join(timeout=10)

        failed_final = self.tracker.list_failed()
        if failed_final:
            logger.warning(f"[Orchestrator] {len(failed_final)} files failed after retries: {failed_final}")

        logger.info(f"[Orchestrator] Complete. {self.tracker.summary()}")

        try:
            self.memory.save()
        except Exception as e:
            logger.debug(f"[Orchestrator] memory.save() failed: {e}")
