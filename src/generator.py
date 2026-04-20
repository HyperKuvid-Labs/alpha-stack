import re
import json
import os
import sys
import time
import logging
from threading import Lock
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from .utils.helpers import get_system_info, clean_agent_output
from .utils.inference import InferenceManager
from .utils.prompt_manager import PromptManager
from .utils.agent_memory import AgentMemory
from .orchestrator import ParallelOrchestrator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generation log — records tool calls & LLM output per file during Phase 2
# ---------------------------------------------------------------------------

class GenerationLog:
    """Thread-safe JSONL logger for generation phase tool calls and outputs."""

    def __init__(self, output_base_dir: str):
        self._path = os.path.join(output_base_dir, ".alpha_stack", "generation_log.jsonl")
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._lock = Lock()

    def log(self, filepath: str, event: str, data: Dict):
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "file": filepath,
            "event": event,
            **data,
        }
        with self._lock:
            try:
                with open(self._path, "a") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass


class TreeNode:
    def __init__(self, value):
        self.value = value
        self.children = []
        self.is_file = False
        self.error_traces = []

    def add_child(self, child_node):
        self.children.append(child_node)


class FileGenerationResult(BaseModel):
    file_content: str = Field(description="The exact content to be written to the file")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DEP_CONTENT_LINES = 200
MAX_CHILD_TURNS = 8
MAX_ORCHESTRATOR_TURNS = 8

# Base tools — shared by both child and orchestrator agents
BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the content of a file that has already been generated. "
                "Blocks until the file is ready. Use this to understand what "
                "a dependency exports before writing import statements or call sites."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Relative path to the file, e.g. 'src/utils.py'"
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_external_packages",
            "description": (
                "Return all external (third-party) packages imported anywhere in the "
                "project so far. Use this when generating manifest files like "
                "requirements.txt, package.json, go.mod, Cargo.toml, etc."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_generated_files",
            "description": "List all project files that have been generated and are available to read.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

# Child-only tool — escalate to orchestrator agent
_ASK_ORCHESTRATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "ask_orchestrator",
        "description": (
            "Ask the project orchestrator for guidance. The orchestrator has the full "
            "project blueprint and can tell you how files connect, what a dependency "
            "exports, correct import paths, and anything about the architecture. "
            "Use this when you are stuck or unsure."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Your question about the project"
                }
            },
            "required": ["question"]
        }
    }
}

CHILD_TOOLS = BASE_TOOLS + [_ASK_ORCHESTRATOR_TOOL]

# Orchestrator-only tools — can inspect + directly fix generated files
_ORCHESTRATOR_ACTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "update_file_code",
            "description": (
                "Overwrite a generated file with corrected content. "
                "Use this for direct fixes when you know exactly what the file should contain."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file (e.g. 'myproject/src/utils.py')"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "Complete new file content"
                    },
                    "change_description": {
                        "type": "string",
                        "description": "Brief description of the change"
                    }
                },
                "required": ["file_path", "new_content", "change_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": (
                "Apply a surgical patch to a generated file. "
                "fix_type: full_rewrite | delete_lines | replace_lines | insert_after_line"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file"
                    },
                    "fix_type": {
                        "type": "string",
                        "description": "full_rewrite | delete_lines | replace_lines | insert_after_line"
                    },
                    "description": {
                        "type": "string",
                        "description": "Why this patch is needed"
                    },
                    "line_start": {
                        "type": "integer",
                        "description": "1-based start line"
                    },
                    "line_end": {
                        "type": "integer",
                        "description": "1-based end line (inclusive)"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "Replacement or insertion content"
                    }
                },
                "required": ["file_path", "fix_type", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "regenerate_file",
            "description": (
                "Re-spawn a child agent to regenerate a file from scratch with your "
                "correction instructions. Use when a file needs a complete rewrite."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file to regenerate"
                    },
                    "corrections": {
                        "type": "string",
                        "description": "Detailed correction instructions for the child agent"
                    }
                },
                "required": ["file_path", "corrections"]
            }
        }
    },
]

ORCHESTRATOR_TOOLS = BASE_TOOLS + _ORCHESTRATOR_ACTION_TOOLS


# ---------------------------------------------------------------------------
# Tool executor factory
# ---------------------------------------------------------------------------

def _make_base_tool_executor(tracker, dep_registry, output_base_dir, registered_files):
    """Returns a callable(name, args) -> str that handles the 3 base tools."""

    def execute(name: str, args: Dict) -> str:
        if name == "read_file":
            req_path = os.path.normpath(args.get("filepath", ""))
            if registered_files is not None and req_path not in registered_files:
                return (
                    f"'{req_path}' is not a file in this project. "
                    f"Available files: {sorted(registered_files)}"
                )
            available = tracker.wait_for_file(req_path)
            if not available:
                return f"'{req_path}' is not available (generation failed). Proceed without it."
            full = os.path.join(output_base_dir, req_path)
            if not os.path.exists(full):
                return f"'{req_path}' does not exist on disk."
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                content = "".join(lines[:MAX_DEP_CONTENT_LINES])
                if len(lines) > MAX_DEP_CONTENT_LINES:
                    content += f"\n... ({len(lines) - MAX_DEP_CONTENT_LINES} more lines truncated)"
                return content
            except Exception as e:
                return f"Error reading file: {e}"

        elif name == "get_external_packages":
            pkgs = dep_registry.all_external_packages()
            return ", ".join(pkgs) if pkgs else "No external packages detected yet."

        elif name == "list_generated_files":
            files = tracker.list_done()
            return "\n".join(sorted(files)) if files else "No files generated yet."

        return f"Unknown tool: {name}"

    return execute


# ---------------------------------------------------------------------------
# Generic agentic loop — used by both child and orchestrator agents
# ---------------------------------------------------------------------------

def _run_agentic_loop(
    system_prompt: str,
    user_message: str,
    tools: List[Dict],
    execute_tool,
    max_turns: int = 8,
    log_callback=None,
) -> Optional[str]:
    """
    Run an agentic tool-calling loop. Returns the final text response or None.
    Handles both Google Gemini and OpenAI/OpenRouter APIs.
    log_callback(event, data) is called for tool calls and final output if provided.
    """
    provider = InferenceManager.get_active_provider()
    provider_name = InferenceManager._active_provider_name or ""

    if provider_name == "google":
        return _run_google_loop(system_prompt, user_message, tools, execute_tool, provider, max_turns, log_callback)
    else:
        return _run_openai_loop(system_prompt, user_message, tools, execute_tool, provider, max_turns, log_callback)


def _run_google_loop(system_prompt, user_message, tools, execute_tool, provider, max_turns, log_callback=None):
    from google.genai import types
    from .utils.inference import retry_api_call

    client = provider.get_client()

    google_tools = types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name=t["function"]["name"],
            description=t["function"]["description"],
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    k: types.Schema(type=types.Type.STRING, description=v.get("description", ""))
                    for k, v in t["function"]["parameters"].get("properties", {}).items()
                },
                required=t["function"]["parameters"].get("required", []),
            )
        )
        for t in tools
    ])

    contents = [{"role": "user", "parts": [{"text": user_message}]}]

    for _ in range(max_turns):
        response = retry_api_call(
            client.models.generate_content,
            model=provider.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[google_tools],
            )
        )
        if not response or not response.candidates:
            break

        parts = response.candidates[0].content.parts
        fn_calls = [p for p in parts if hasattr(p, "function_call") and p.function_call]

        if fn_calls:
            contents.append({"role": "model", "parts": [{"function_call": p.function_call} for p in fn_calls]})
            tool_results = []
            for p in fn_calls:
                fc = p.function_call
                tool_out = execute_tool(fc.name, dict(fc.args))
                if log_callback:
                    log_callback("tool_call", {"tool": fc.name, "args": dict(fc.args), "result_preview": str(tool_out)[:300]})
                tool_results.append({"function_response": {"name": fc.name, "response": {"result": tool_out}}})
            contents.append({"role": "user", "parts": tool_results})
        else:
            text = response.text or None
            if log_callback and text:
                log_callback("output", {"length": len(text), "preview": text[:200]})
            return text

    return None


def _run_openai_loop(system_prompt, user_message, tools, execute_tool, provider, max_turns, log_callback=None):
    client = provider.get_client()
    messages: List[Dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for _ in range(max_turns):
        try:
            completion = client.chat.completions.create(
                model=provider.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
        except Exception as e:
            print(f"[agentic_loop] API error: {e}")
            break

        msg = completion.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_out = execute_tool(tc.function.name, args)
                if log_callback:
                    log_callback("tool_call", {"tool": tc.function.name, "args": args, "result_preview": str(tool_out)[:300]})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_out,
                })
        else:
            text = msg.content or None
            if log_callback and text:
                log_callback("output", {"length": len(text), "preview": text[:200]})
            return text

    return None


# ---------------------------------------------------------------------------
# Orchestrator tool executor (base + action tools)
# ---------------------------------------------------------------------------

def _make_orchestrator_tool_executor(tracker, dep_registry, output_base_dir, registered_files, orchestrator_ref, pm, memory=None):
    """
    Returns a callable(name, args) -> str for the orchestrator agent.
    Handles base tools + action tools (update_file_code, patch_file, regenerate_file).
    Optionally records actions to an AgentMemory instance.
    """
    from .utils.tools import ToolHandler

    base_execute = _make_base_tool_executor(tracker, dep_registry, output_base_dir, registered_files)

    # ToolHandler for file write operations — uses output_base_dir as root
    # so filepaths like 'myproject/src/main.py' resolve correctly
    tool_handler = ToolHandler(project_root=output_base_dir)

    def execute(name: str, args: Dict) -> str:
        # Base tools
        if name in ("read_file", "get_external_packages", "list_generated_files"):
            return base_execute(name, args)

        # Regenerate — re-spawn child agent with corrections
        if name == "regenerate_file":
            filepath = os.path.normpath(args.get("file_path", ""))
            corrections = args.get("corrections", "")

            if filepath not in orchestrator_ref._tasks:
                return json.dumps({"success": False, "error": f"'{filepath}' is not a registered file"})

            prompt_rules = orchestrator_ref._tasks[filepath]["prompt_rules"]
            if corrections:
                prompt_rules += "\n\nCorrections from orchestrator:\n" + corrections

            result = generate_file(
                filepath=filepath,
                prompt_rules=prompt_rules,
                pm=pm,
                tracker=tracker,
                dep_registry=dep_registry,
                output_base_dir=output_base_dir,
                registered_files=registered_files,
                blueprint_context=orchestrator_ref.blueprint_context,
            )

            if result and result.file_content:
                full_path = os.path.join(output_base_dir, filepath)
                os.makedirs(os.path.dirname(full_path) or output_base_dir, exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(result.file_content)
                orchestrator_ref._register_deps(filepath, full_path, content=result.file_content)
                tracker.mark_done(filepath)
                if memory:
                    memory.record_regenerate(filepath, corrections[:80])
                return json.dumps({"success": True, "message": f"Regenerated {filepath}"})

            return json.dumps({"success": False, "error": f"Failed to regenerate {filepath}"})

        # update_file_code, patch_file — delegate to ToolHandler
        if name in ("update_file_code", "patch_file"):
            result = tool_handler.handle_function_call(name, args)
            # After modifying a file, update the dep registry
            filepath = os.path.normpath(args.get("file_path", ""))
            if isinstance(result, dict) and result.get("success"):
                full_path = os.path.join(output_base_dir, filepath)
                if os.path.exists(full_path):
                    orchestrator_ref._register_deps(filepath, full_path)
                if memory:
                    desc = args.get("change_description", args.get("description", ""))
                    memory.record_edit(0, filepath, desc)
            return json.dumps(result) if isinstance(result, dict) else str(result)

        return f"Unknown tool: {name}"

    return execute


# ---------------------------------------------------------------------------
# Orchestrator agent call
# ---------------------------------------------------------------------------

def call_orchestrator_agent(
    question: str,
    filepath: str,
    blueprint_context: Dict[str, Any],
    tracker,
    dep_registry,
    output_base_dir: str,
    registered_files: set,
    pm: PromptManager,
    orchestrator_ref=None,
    memory=None,
) -> str:
    """
    Call the orchestrator agent with the full blueprint. Used for:
      1. Child agent's ask_orchestrator tool
      2. Worker retry on total failure
    Returns the orchestrator's text guidance.
    """
    if orchestrator_ref is not None:
        execute_tool = _make_orchestrator_tool_executor(
            tracker, dep_registry, output_base_dir, registered_files,
            orchestrator_ref, pm, memory=memory,
        )
        tools = ORCHESTRATOR_TOOLS
    else:
        execute_tool = _make_base_tool_executor(tracker, dep_registry, output_base_dir, registered_files)
        tools = BASE_TOOLS

    system_prompt = pm.render(
        "orchestrator_agent.j2",
        filepath=filepath,
        blueprint_context=blueprint_context,
        orchestrator_memory=memory.render() if memory else "",
    )

    result = _run_agentic_loop(
        system_prompt=system_prompt,
        user_message=question,
        tools=tools,
        execute_tool=execute_tool,
        max_turns=MAX_ORCHESTRATOR_TURNS,
    )

    response = result or "Orchestrator could not provide guidance."
    if memory:
        memory.record_guidance(filepath, question[:80])
    return response


# ---------------------------------------------------------------------------
# Batch orchestrator — processes queued queries from multiple children
# ---------------------------------------------------------------------------

def process_orchestrator_batch(
    queries: List[Dict],
    blueprint_context: Dict[str, Any],
    tracker,
    dep_registry,
    output_base_dir: str,
    registered_files: set,
    orchestrator_ref,
    pm: PromptManager,
    history: List[Dict],
    memory=None,
) -> Dict[str, str]:
    """
    Process a batch of orchestrator queries. Returns {query_id: response_text}.
    Single queries go through call_orchestrator_agent directly.
    Multiple queries are batched into one LLM call for coordinated responses.
    """
    import re as _re

    # Single query — direct processing (no batch overhead)
    if len(queries) == 1:
        q = queries[0]
        result = call_orchestrator_agent(
            question=q["question"],
            filepath=q["filepath"],
            blueprint_context=blueprint_context,
            tracker=tracker,
            dep_registry=dep_registry,
            output_base_dir=output_base_dir,
            registered_files=registered_files,
            pm=pm,
            orchestrator_ref=orchestrator_ref,
            memory=memory,
        )
        return {q["id"]: result}

    # Multiple queries — batch processing
    execute_tool = _make_orchestrator_tool_executor(
        tracker, dep_registry, output_base_dir, registered_files,
        orchestrator_ref, pm, memory=memory,
    )

    system_prompt = pm.render(
        "orchestrator_agent.j2",
        filepath="multiple agents",
        blueprint_context=blueprint_context,
        orchestrator_memory=memory.render() if memory else "",
    )

    # Build user message with history + all queries
    parts = []
    if history:
        parts.append("### Recent Query History (for context)")
        for h in history[-5:]:
            parts.append(f"- Agent for `{h['filepath']}` asked: {h['question']}")
            parts.append(f"  You responded: {h['response'][:200]}...")
        parts.append("")

    parts.append(f"### {len(queries)} Queries from Child Agents\n")
    for i, q in enumerate(queries, 1):
        parts.append(f"**[QUERY {i}]** From agent generating `{q['filepath']}`:")
        parts.append(q["question"])
        parts.append("")

    parts.append("### Instructions")
    parts.append("Analyze all queries together. Use tools to investigate and fix issues if needed.")
    parts.append("Then respond with guidance for EACH query using this exact format:\n")
    for i, q in enumerate(queries, 1):
        parts.append(f"[RESPONSE {i}]")
        parts.append(f"(your guidance for the agent generating `{q['filepath']}`)\n")

    user_message = "\n".join(parts)

    result = _run_agentic_loop(
        system_prompt=system_prompt,
        user_message=user_message,
        tools=ORCHESTRATOR_TOOLS,
        execute_tool=execute_tool,
        max_turns=MAX_ORCHESTRATOR_TURNS,
    )

    if not result:
        return {q["id"]: "Orchestrator could not provide guidance." for q in queries}

    # Parse individual responses from the batch output
    responses = {}
    for i, q in enumerate(queries, 1):
        pattern = rf"\[RESPONSE {i}\](.*?)(?=\[RESPONSE \d+\]|$)"
        match = _re.search(pattern, result, _re.DOTALL)
        if match:
            responses[q["id"]] = match.group(1).strip()
        else:
            # Fallback: give full response to all
            responses[q["id"]] = result.strip()

        if memory:
            memory.record_guidance(q["filepath"], q["question"][:80])

    return responses


# ---------------------------------------------------------------------------
# Child agent: generate a single file
# ---------------------------------------------------------------------------

def generate_file(
    filepath: str,
    prompt_rules: str,
    pm: PromptManager,
    tracker,
    dep_registry,
    output_base_dir: str,
    registered_files: Optional[set] = None,
    blueprint_context: Optional[Dict[str, Any]] = None,
    orchestrator_mailbox=None,
    gen_log: Optional[GenerationLog] = None,
) -> Optional[FileGenerationResult]:
    # Base tool executor (read_file, get_external_packages, list_generated_files)
    execute_base = _make_base_tool_executor(tracker, dep_registry, output_base_dir, registered_files)

    # Log callback for this file
    def log_cb(event, data):
        if gen_log:
            gen_log.log(filepath, event, data)

    # Child tool executor — adds ask_orchestrator on top of base
    def execute_tool(name: str, args: Dict) -> str:
        if name == "ask_orchestrator":
            question = args.get("question", "")

            # Route through mailbox if available (batched with other children's queries)
            if orchestrator_mailbox is not None:
                return orchestrator_mailbox.ask(question, filepath)

            # Fallback: direct call (used by regenerated children from orchestrator)
            if blueprint_context is None:
                return "Orchestrator not available — no blueprint context."
            return call_orchestrator_agent(
                question=question,
                filepath=filepath,
                blueprint_context=blueprint_context,
                tracker=tracker,
                dep_registry=dep_registry,
                output_base_dir=output_base_dir,
                registered_files=registered_files or set(),
                pm=pm,
            )
        return execute_base(name, args)

    system_prompt = pm.render("file_generation.j2", filepath=filepath, prompt_rules=prompt_rules)

    text = _run_agentic_loop(
        system_prompt=system_prompt,
        user_message="Generate the file now.",
        tools=CHILD_TOOLS,
        execute_tool=execute_tool,
        max_turns=MAX_CHILD_TURNS,
        log_callback=log_cb,
    )

    if text:
        return FileGenerationResult(file_content=clean_agent_output(text))
    return None


# ---------------------------------------------------------------------------
# Architecture planning (Phase 0 — pure design, no code, no file structure)
# ---------------------------------------------------------------------------

def generate_architecture_plan(prompt: str, pm, provider_name: Optional[str] = None) -> Optional[str]:
    """Generate a comprehensive architecture document (Markdown) from the user prompt."""
    provider = InferenceManager.get_active_provider()
    provider_name = InferenceManager._active_provider_name or ""
    system_info = get_system_info()
    system_instruction = pm.render_architecture_planning(user_prompt=prompt, system_info=system_info)

    if provider_name == "google":
        from google.genai import types
        from .utils.inference import retry_api_call
        client = provider.get_client()
        response = retry_api_call(
            client.models.generate_content,
            model=provider.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                systemInstruction=system_instruction,
            )
        )
        if not response or not response.text:
            return None
        return response.text.strip()
    else:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]
        try:
            client = provider.get_client()
            completion = client.chat.completions.create(
                model=provider.model,
                messages=messages,
            )
            text = completion.choices[0].message.content
            return text.strip() if text else None
        except Exception as e:
            print(f"Error generating architecture plan: {e}")
            return None


# ---------------------------------------------------------------------------
# Blueprint generation (Phase 1)
# ---------------------------------------------------------------------------

class ProjectBlueprint(BaseModel):
    software_blueprint_details: Dict[str, Any] = Field(description="Dictionary containing core project intelligence, overview, and features")
    folder_structure: str = Field(description="Raw ASCII string representing the exact directory and file structure tree")
    file_formats: Dict[str, Any] = Field(description="Dictionary mapping precise filepaths from the folder structure to instructions on how each file must be generated")


def generate_project_blueprint(prompt: str, pm, provider_name: Optional[str] = None, architecture_content: Optional[str] = None) -> Optional[ProjectBlueprint]:
    provider = InferenceManager.get_active_provider()
    provider_name = InferenceManager._active_provider_name or ""
    system_info = get_system_info()
    system_instruction = pm.render_project_blueprint(user_prompt=prompt, system_info=system_info, architecture_content=architecture_content)

    if provider_name == "google":
        from google.genai import types
        from .utils.inference import retry_api_call
        client = provider.get_client()
        response = retry_api_call(
            client.models.generate_content,
            model=provider.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                systemInstruction=system_instruction,
                response_mime_type="application/json",
                response_schema=ProjectBlueprint,
            )
        )
        if not response or not response.text:
            return None
        try:
            data = json.loads(response.text)
            return ProjectBlueprint(**data)
        except (json.JSONDecodeError, ValueError):
            return None

    else:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]
        client = provider.get_client()

        # NOTE: we deliberately skip `client.beta.chat.completions.parse(
        # response_format=ProjectBlueprint)`. OpenAI's strict-schema mode
        # rejects `Dict[str, Any]` fields (no fixed property set) and most
        # providers silently return an empty `{}` for `file_formats` rather
        # than raising — which produces a valid Pydantic object with no
        # content and zero files to generate. Plain JSON-mode completion +
        # manual extraction is the reliable path for this schema.

        json_nudge = (
            "Respond with EXACTLY one JSON object matching the schema described in the system "
            "instruction. No markdown fences, no prose before or after, no explanations."
        )
        nudged = messages + [{"role": "system", "content": json_nudge}]

        raw_content: Optional[str] = None
        last_err: Optional[Exception] = None
        for kwargs in (
            {"response_format": {"type": "json_object"}},
            {},
        ):
            try:
                completion = client.chat.completions.create(
                    model=provider.model,
                    messages=nudged,
                    **kwargs,
                )
                raw_content = (completion.choices[0].message.content or "").strip()
                break
            except Exception as call_err:
                last_err = call_err
                print(
                    f"[blueprint] completion call failed ({kwargs or 'plain'}): {call_err}",
                    file=sys.stderr,
                )

        if raw_content is None:
            print(
                f"[blueprint] all completion attempts failed for {provider.model}; "
                f"last error: {last_err}",
                file=sys.stderr,
            )
            return None

        json_str = _extract_json_object(raw_content)
        if not json_str:
            snippet = raw_content[:400].replace("\n", " ")
            print(
                f"[blueprint] could not locate JSON object in response. "
                f"Model: {provider.model}. First 400 chars: {snippet!r}",
                file=sys.stderr,
            )
            return None

        try:
            data = json.loads(json_str)
            return ProjectBlueprint(**data)
        except Exception as parse_err:
            snippet = json_str[:400].replace("\n", " ")
            print(
                f"[blueprint] JSON parse/validate failed: {parse_err}. "
                f"Extracted: {snippet!r}",
                file=sys.stderr,
            )
            return None


def _extract_json_object(text: str) -> Optional[str]:
    """Pull the first top-level JSON object out of a model response.

    Tries:
      1. ```json ... ``` fenced block
      2. Balanced-brace walk from the first '{'

    Returns the substring or None.
    """
    if not text:
        return None

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


# ---------------------------------------------------------------------------
# Tree parser (unchanged)
# ---------------------------------------------------------------------------

def generate_tree(resp, project_name="root"):
    content = resp.strip().replace('```', '').strip()
    lines = content.split('\n')
    tree_line_pattern = re.compile(r'^(?:[│|]\s*)*(?:├──\s*|└──\s*|\|--\s*|\+--\s*|`--\s*|\|___\s*)?([^│├└|+#\n]+?)(?:/)?(?:\s*#.*)?$', re.IGNORECASE)

    root = None
    root_name = None
    root_line_index = -1

    for i, line in enumerate(lines):
        if not line.strip():
            continue
        match = tree_line_pattern.match(line.strip())
        if match:
            raw_name = match.group(1)
            root_name = re.sub(r'^[│├└─|`+\-\s]+', '', raw_name).strip().rstrip('/')
        else:
            root_name = line.strip()
            if '#' in root_name:
                root_name = root_name.split('#')[0].strip()
            root_name = re.sub(r'^[│├└─|`+\-\s]+', '', root_name).strip().rstrip('/')
        if root_name:
            root_name = root_name.replace(' ', '_')
            root = TreeNode(root_name)
            root_line_index = i
            break

    if not root:
        root = TreeNode(project_name)
        root_line_index = -1

    stack = [root]

    for i, line in enumerate(lines):
        if not line.strip() or i <= root_line_index:
            continue

        indent = 0
        temp_line = line
        while True:
            if temp_line.startswith('│   ') or temp_line.startswith('|   ') or temp_line.startswith('    '):
                temp_line = temp_line[4:]
                indent += 1
            elif temp_line.startswith('│ ') or temp_line.startswith('| '):
                temp_line = temp_line[2:]
                indent += 1
            elif temp_line.startswith('\t'):
                temp_line = temp_line[1:]
                indent += 1
            else:
                break

        match = tree_line_pattern.match(line.strip())
        if not match:
            name = line.strip()
            if '#' in name:
                name = name.split('#')[0].strip()
            name = re.sub(r'^[│├└─|`+\-\s]+', '', name).strip()
        else:
            raw_name = match.group(1)
            name = re.sub(r'^[│├└─|`+\-\s]+', '', raw_name).strip()

        name = name.rstrip('/')
        name = name.replace(' ', '_')

        if not name:
            continue

        node = TreeNode(name)

        if indent == 0:
            root.add_child(node)
            stack = [root, node]
        else:
            while len(stack) <= indent:
                stack.append(root)
            while len(stack) > indent + 1:
                stack.pop()
            if stack:
                stack[-1].add_child(node)
            stack.append(node)

    def mark_files_and_dirs(node):
        if not node.children:
            node.is_file = True
        else:
            node.is_file = False
            for child in node.children:
                mark_files_and_dirs(child)

    mark_files_and_dirs(root)
    return root


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_project(
    user_prompt,
    output_base_dir,
    on_status=None,
    provider_name: Optional[str] = None,
    model_override: Optional[str] = None,
    **_unused_kwargs,
):
    from .utils.dependencies import DependencyAnalyzer
    from .testing.testing import run_testing_pipeline
    from .utils.error_tracker import ErrorTracker

    def emit(event_type, message, **kwargs):
        if on_status:
            on_status(event_type, message, **kwargs)

    pm = PromptManager()

    provider_name = provider_name or InferenceManager.get_default_provider()
    InferenceManager.initialize(provider_name, model_override=model_override)

    emit("step", "Designing system architecture...")
    architecture_content = generate_architecture_plan(user_prompt, pm, provider_name)

    if not architecture_content:
        emit("error", "Failed to generate architecture plan.")
        return None

    alpha_stack_dir = os.path.join(output_base_dir, ".alpha_stack")
    os.makedirs(alpha_stack_dir, exist_ok=True)
    arch_path = os.path.join(alpha_stack_dir, "architecture.md")
    with open(arch_path, "w") as f:
        f.write(architecture_content)
    emit("step", f"Architecture document saved to {arch_path}")

    emit("step", "Planning file structure and generating project blueprint...")
    blueprint = generate_project_blueprint(user_prompt, pm, provider_name, architecture_content=architecture_content)

    if not blueprint:
        emit(
            "error",
            "Failed to generate project blueprint. "
            "The model returned malformed JSON or rejected the completion call. "
            "Check the log above for the underlying error, then try a different model "
            "(e.g. google/gemini-2.5-pro, openai/gpt-4o, anthropic/claude-3.5-sonnet).",
        )
        return None

    if not blueprint.file_formats or not blueprint.folder_structure.strip():
        emit(
            "error",
            f"Blueprint returned empty content (file_formats={len(blueprint.file_formats or {})}, "
            f"folder_structure={'present' if blueprint.folder_structure.strip() else 'EMPTY'}). "
            "The model produced a valid JSON shell but didn't populate it. "
            "Try a stronger model (google/gemini-2.5-pro, openai/gpt-4o, anthropic/claude-3.5-sonnet) "
            "or rephrase the prompt with more detail.",
        )
        return None

    software_blueprint = blueprint.software_blueprint_details
    folder_struc = blueprint.folder_structure
    file_format = blueprint.file_formats
    file_output_format = file_format

    emit("step", "Building project tree and generating files...")
    folder_tree = generate_tree(folder_struc, project_name="")
    dependency_analyzer = DependencyAnalyzer()
    os.makedirs(output_base_dir, exist_ok=True)

    # Build orchestrator with full blueprint context
    orchestrator = ParallelOrchestrator(output_base_dir=output_base_dir, max_workers=20)
    orchestrator.set_blueprint(
        software_blueprint=software_blueprint,
        folder_structure=folder_struc,
        file_formats=file_format,
    )

    for filepath, details in file_format.items():
        prompt_rules = details.get("purpose", "")
        orchestrator.add_node(filepath, prompt_rules)

    start_time = time.time()
    orchestrator.execute()

    project_root_path = os.path.join(output_base_dir, folder_tree.value)

    if not os.path.exists(project_root_path):
        return None

    emit("step", "Starting dependency analysis for entire project...")
    dependency_analyzer.analyze_project_files(project_root_path, folder_tree=folder_tree, folder_structure=folder_struc)

    from .utils.dependencies import build_dependency_graph_tree
    dep_graph = build_dependency_graph_tree(project_root_path, dependency_analyzer)
    print("\n[dependency_graph]\n" + dep_graph + "\n")

    error_tracker = ErrorTracker(project_root_path, folder_tree)

    emit("step", "Running testing pipeline...")

    testing_results = run_testing_pipeline(
        project_root=project_root_path,
        software_blueprint=software_blueprint,
        folder_structure=folder_struc,
        file_output_format=file_output_format,
        pm=pm,
        error_tracker=error_tracker,
        dependency_analyzer=dependency_analyzer,
        on_status=on_status,
        provider_name=provider_name,
    )

    end_time = time.time()
    elapsed = end_time - start_time

    overall_success = testing_results.get("success", False)

    return {
        "project_path": project_root_path,
        "success": overall_success,
        "testing": testing_results,
        "elapsed_time": elapsed
    }
