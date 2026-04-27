import argparse
import sys
import os
import io
import json
import shutil
import contextlib
import subprocess
import traceback
from pathlib import Path

_REAL_STDOUT = sys.__stdout__


def normalize_problem_statement_language(raw_value):
    value = (raw_value or "").strip().lower()
    if not value:
        return "others"
    if value in {"cuda", "others"}:
        return value
    return None


def prompt_problem_statement_language():
    while True:
        choice = input("Project language profile (cuda/others) [others]: ").strip().lower()
        normalized = normalize_problem_statement_language(choice)
        if normalized:
            return normalized
        print("Please choose either 'cuda' or 'others'.")


def status_handler(event_type, message, **kwargs):
    if event_type == "step":
        step_num = getattr(status_handler, "_step_num", 0) + 1
        setattr(status_handler, "_step_num", step_num)
        print(f"[{step_num}] {message}")
        return

    if event_type == "progress":
        print(f"   {message}")
    elif event_type == "success":
        print(f"{message}")
    elif event_type == "error":
        print(f"{message}")
    elif event_type == "warning":
        print(f" {message}")
    else:
        print(f"   {message}")


def cmd_generate(args):
    from .generator import generate_project

    setattr(status_handler, "_step_num", 0)

    print("=" * 80)
    print("ALPHASTACK - Project Generator")
    print("=" * 80)
    print()

    user_prompt = args.prompt
    output_dir = args.output or "./created_projects"

    if not user_prompt:
        user_prompt = input("Enter your project description: ").strip()

    if not user_prompt:
        print("Project description is required!")
        return 1

    problem_statement_language = normalize_problem_statement_language(getattr(args, "language", None))
    if not problem_statement_language:
        problem_statement_language = prompt_problem_statement_language()

    print(f"\nProject: {user_prompt[:50]}...")
    print(f"Output: {output_dir}")
    print(f"Language profile: {problem_statement_language}")
    print()

    provider_name = getattr(args, "provider", None)
    result = generate_project(
        user_prompt,
        output_dir,
        on_status=status_handler,
        provider_name=provider_name,
        problem_statement_language=problem_statement_language,
    )

    if not result:
        print("\nProject generation failed")
        return 1

    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    dep_result = result.get("dependency_resolution", {})
    testing_result = result.get("testing", {})
    success = result.get("success", False)

    print(f"\nDependency Resolution: {'SUCCESS' if dep_result.get('success') else 'FAILED'}")
    if not dep_result.get('success'):
        remaining = dep_result.get("remaining_errors", [])
        if remaining:
            print(f"   {len(remaining)} remaining issues")

    tests_passed = testing_result.get("tests_success", False)
    print(f"\nSandboxed Tests: {'SUCCESS' if tests_passed else 'FAILED'}")
    print(f"   Tool calls: {testing_result.get('tool_calls', 0)}")
    if testing_result.get("gave_up"):
        print("   Planner gave up before tests passed.")

    print(f"\n{'=' * 80}")
    if success:
        print("PROJECT GENERATION: COMPLETE SUCCESS")
        print("\n   All dependencies resolved")
        print("   All tests passed in sandbox")
        print("\n   The project is ready to use!")
    else:
        print("PROJECT GENERATION: INCOMPLETE")
        print("\n   Some steps may require manual fixes")
    print(f"\nTime: {result.get('elapsed_time', 0):.2f}s")
    print(f" Location: {result.get('project_path', 'unknown')}")
    print("=" * 80)

    return 0 if success else 1


def cmd_list(args):
    output_dir = args.output or "./created_projects"

    if not os.path.exists(output_dir):
        print(f" No projects found in {output_dir}")
        return 0

    print(f" Projects in {output_dir}:")
    print("-" * 40)

    projects = []
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path) and not item.startswith('.'):
            projects.append(item)

    if not projects:
        print("   (no projects found)")
        return 0

    for project in sorted(projects):
        project_path = os.path.join(output_dir, project)
        readme_exists = os.path.exists(os.path.join(project_path, "README.md"))

        readme_status = "📖" if readme_exists else ""

        print(f"   📄 {project} {readme_status}")

    print("-" * 40)
    print(f"   Total: {len(projects)} project(s)")

    return 0


def cmd_clean(args):
    output_dir = args.output or "./created_projects"

    if not os.path.exists(output_dir):
        print(f"📁 Directory {output_dir} does not exist")
        return 0

    if not args.force:
        confirm = input(f"⚠️  Delete all projects in {output_dir}? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("   Cancelled")
            return 0

    import shutil

    deleted = 0
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path) and not item.startswith('.'):
            try:
                shutil.rmtree(item_path)
                print(f"   🗑️  Deleted {item}")
                deleted += 1
            except Exception as e:
                print(f"   Failed to delete {item}: {e}")

    print(f"\nDeleted {deleted} project(s)")
    return 0


def cmd_setup(args):
    """Command wrapper for API setup."""
    try:
        from .tui import setup_api_key
        setup_api_key()
        return 0
    except ImportError:
        print("⚠️  TUI dependencies missing. Please install 'rich' and 'prompt_toolkit'.")
        return 1


def cmd_blueprint_smoke(args):
    from .generator import generate_project_blueprint
    from .utils.prompt_manager import PromptManager

    prompt = args.prompt
    if not prompt:
        prompt = input("Enter blueprint prompt: ").strip()

    if not prompt:
        print("Project description is required!")
        return 1

    provider_name = getattr(args, "provider", None) or "openrouter"
    problem_statement_language = normalize_problem_statement_language(getattr(args, "language", None)) or "others"

    print("=" * 80)
    print("ALPHASTACK - Blueprint Smoke Test")
    print("=" * 80)
    print(f"Provider: {provider_name}")
    print(f"Language profile: {problem_statement_language}")

    pm = PromptManager()
    blueprint = generate_project_blueprint(
        prompt=prompt,
        pm=pm,
        provider_name=provider_name,
        problem_statement_language=problem_statement_language,
    )
    print(f"blueprint: {blueprint}")

    if not blueprint:
        print("\nBlueprint generation failed")
        return 1

    print("\nBlueprint generation succeeded")
    print(f"Top-level keys: {list(blueprint.software_blueprint_details.keys())}")
    print(f"Folder structure length: {len(blueprint.folder_structure)} chars")
    print(f"File format entries: {len(blueprint.file_formats)}")
    return 0


def _emit(req_id, type_, message="", data=None):
    payload = {"id": req_id, "type": type_, "message": message}
    if data is not None:
        payload["data"] = data
    line = json.dumps(payload, default=str, ensure_ascii=False)
    print(line, file=_REAL_STDOUT, flush=True)


class _RPCStreamWriter(io.TextIOBase):
    def __init__(self, req_id, stream_name):
        self._req_id = req_id
        self._stream = stream_name
        self._buf = ""

    def writable(self):
        return True

    def write(self, text):
        if not text:
            return 0
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.rstrip()
            if line:
                _emit(self._req_id, "log", line, data={"stream": self._stream})
        return len(text)

    def flush(self):
        if self._buf.strip():
            _emit(self._req_id, "log", self._buf.strip(), data={"stream": self._stream})
        self._buf = ""


def _load_provider_options_local():
    config_path = Path(__file__).with_name("providers.json")
    fallback = (["openrouter", "google", "openai", "prime_intellect"], "openrouter")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return fallback

    providers = [
        name.strip().lower()
        for name in (config.get("model_providers") or {}).keys()
        if isinstance(name, str) and name.strip()
    ]
    if not providers:
        return fallback
    default = str(config.get("default_provider", "")).strip().lower()
    if default not in providers:
        default = providers[0]
    return providers, default


def _rpc_list_providers(req):
    from .config import get_provider_api_key

    providers, default = _load_provider_options_local()
    model_defaults = _load_provider_model_defaults()
    payload = []
    for name in providers:
        needs_key = True
        has_key = bool(get_provider_api_key(name)) if needs_key else True
        payload.append({
            "name": name,
            "needs_api_key": needs_key,
            "has_api_key": has_key,
            "is_default": name == default,
            "default_model": model_defaults.get(name, ""),
        })
    _emit(req.get("id"), "result", "", data={"providers": payload, "default": default})


def _load_provider_model_defaults():
    config_path = Path(__file__).with_name("providers.json")
    try:
        with open(config_path, "r") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for name, entry in (cfg.get("model_providers") or {}).items():
        if isinstance(entry, dict):
            out[str(name).strip().lower()] = entry.get("model", "")
    return out


def _rpc_get_provider_status(req):
    from .config import get_provider_api_key

    provider = (req.get("params") or {}).get("provider", "")
    has_key = bool(get_provider_api_key(provider))
    _emit(req.get("id"), "result", "", data={"provider": provider, "has_api_key": has_key})


def _rpc_set_api_key(req):
    from .config import set_provider_api_key

    params = req.get("params") or {}
    provider = params.get("provider", "")
    api_key = params.get("api_key", "")
    if not provider or not api_key:
        _emit(req.get("id"), "result", "", data={"ok": False, "error": "provider and api_key required"})
        return
    ok = set_provider_api_key(provider, api_key)
    _emit(req.get("id"), "result", "", data={"ok": bool(ok), "provider": provider})


def _rpc_ping_model(req):
    """Validate a (provider, model, api_key) triple by issuing a tiny completion.

    Returns {"ok": bool, "provider": str, "model": str, "message": str, "error": str}.
    The TUI uses this to bounce the user back to the model screen if the
    provider rejects the model name or the API key is wrong.
    """
    req_id = req.get("id")
    params = req.get("params") or {}
    provider = (params.get("provider") or "").strip()
    model = (params.get("model") or "").strip()
    api_key = params.get("api_key")

    if not provider or not model:
        _emit(req_id, "result", "", data={
            "ok": False, "provider": provider, "model": model,
            "error": "provider and model are required",
        })
        return

    if api_key:
        try:
            from .config import set_provider_api_key
            set_provider_api_key(provider, api_key)
        except Exception:
            pass

    try:
        from .utils.inference import InferenceManager
        InferenceManager.reset()
        inf = InferenceManager.initialize(
            provider_name=provider, validate=True, model_override=model
        )
    except Exception as exc:
        _emit(req_id, "result", "", data={
            "ok": False, "provider": provider, "model": model,
            "error": f"init failed: {exc}",
        })
        return

    try:
        from .utils.prompt_manager import PromptManager
        greeting = PromptManager().render(
            "ping_greeting.j2",
            provider=provider,
            model=model,
            description=(
                "an AI-powered project generator that turns natural-language "
                "project descriptions into production-ready codebases"
            ),
        )
    except Exception as exc:
        _emit(req_id, "result", "", data={
            "ok": False, "provider": provider, "model": model,
            "error": f"greeting prompt render failed: {exc}",
        })
        return

    try:
        messages = inf.create_initial_message(greeting)
        response = inf.call_model(messages=messages)
        text = (inf.extract_text(response) or "").strip()
    except Exception as exc:
        _emit(req_id, "result", "", data={
            "ok": False, "provider": provider, "model": model,
            "error": f"ping failed: {exc}",
        })
        return

    if not text:
        _emit(req_id, "result", "", data={
            "ok": False, "provider": provider, "model": model,
            "error": "model returned empty response",
        })
        return

    _emit(req_id, "result", "", data={
        "ok": True, "provider": provider, "model": model,
        "message": text[:200],
    })


def _rpc_generate(req):
    from .generator import generate_project

    req_id = req.get("id")
    params = req.get("params") or {}
    prompt = params.get("prompt", "")
    output_dir = params.get("output_dir", "")
    provider = params.get("provider")
    model = params.get("model") or None
    language = params.get("language", "others")

    def on_status(event_type, message, **kwargs):
        _emit(req_id, event_type, message, data=(kwargs or None))

    stdout_writer = _RPCStreamWriter(req_id, "stdout")
    stderr_writer = _RPCStreamWriter(req_id, "stderr")
    try:
        with contextlib.redirect_stdout(stdout_writer), contextlib.redirect_stderr(stderr_writer):
            result = generate_project(
                prompt,
                output_dir,
                on_status=on_status,
                provider_name=provider,
                model_override=model,
                problem_statement_language=language,
            )
    finally:
        stdout_writer.flush()
        stderr_writer.flush()

    if not isinstance(result, dict):
        result = {"success": False, "project_path": "", "elapsed_time": 0}
    _emit(req_id, "result", "", data=result)


def cmd_json_rpc():
    """Long-running JSON-RPC loop driven by the Go TUI."""
    handlers = {
        "list_providers": _rpc_list_providers,
        "get_provider_status": _rpc_get_provider_status,
        "set_api_key": _rpc_set_api_key,
        "ping_model": _rpc_ping_model,
        "generate": _rpc_generate,
    }

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _emit(None, "error", f"invalid json: {exc}")
            continue

        action = req.get("action")
        handler = handlers.get(action)
        req_id = req.get("id")
        if not handler:
            _emit(req_id, "error", f"unknown action: {action}")
            _emit(req_id, "result", "", data={"success": False, "error": f"unknown action: {action}"})
            continue

        try:
            handler(req)
        except KeyboardInterrupt:
            _emit(req_id, "error", "cancelled")
            _emit(req_id, "result", "", data={"success": False, "cancelled": True})
            return 0
        except Exception as exc:
            _emit(req_id, "error", str(exc), data={"traceback": traceback.format_exc()})
            _emit(req_id, "result", "", data={"success": False, "error": str(exc)})

    return 0


def _find_go_tui():
    candidates = [os.environ.get("ALPHASTACK_TUI_BIN")]
    candidates.append(shutil.which("alphastack-tui"))
    repo_bin = Path(__file__).resolve().parent.parent / "bin" / "alphastack-tui"
    candidates.append(str(repo_bin))
    for cand in candidates:
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def interactive_mode():
    """Launches the interactive TUI mode."""
    bin_path = _find_go_tui()
    if bin_path and not os.environ.get("ALPHASTACK_NO_GO_TUI"):
        env = os.environ.copy()
        env.setdefault("ALPHASTACK_PYTHON", sys.executable)
        try:
            return subprocess.run([bin_path], env=env).returncode
        except KeyboardInterrupt:
            return 130

    try:
        from .tui import display_logo, get_user_input, StatusDisplay, print_success, print_error
    except ImportError:
        # Fallback if dependencies are missing
        print("  TUI dependencies missing. Run 'pip install alphastack[tui]' or install rich, pyfiglet, prompt_toolkit.")
        # Create dummy args for generic flow
        dummy_args = argparse.Namespace(prompt=None, output=None, language=None)
        return cmd_generate(dummy_args)

    display_logo()

    try:
        user_prompt, output_dir, problem_statement_language, provider_name = get_user_input()
    except KeyboardInterrupt:
        print("\n Exiting...")
        return 0

    from .generator import generate_project

    # Create status display
    status_display = StatusDisplay()

    def tui_status_handler(event_type, message, **kwargs):
        status_display.update(message, event_type)

    with status_display:
        try:
            with contextlib.redirect_stdout(status_display.stdout_stream()), contextlib.redirect_stderr(status_display.stderr_stream()):
                result = generate_project(
                    user_prompt,
                    output_dir,
                    on_status=tui_status_handler,
                    provider_name=provider_name,
                    problem_statement_language=problem_statement_language,
                )
        except Exception as exc:
            status_display.add_exception("Unhandled exception during project generation", exc)
            result = None

    if not result or not isinstance(result, dict):
        if status_display.last_error:
            print_error(f"Project generation failed: {status_display.last_error}")
        else:
            print_error("Project generation failed before producing a result.")
        if status_display.last_traceback:
            console_preview = "\n".join(status_display.last_traceback.strip().splitlines()[-8:])
            print_error(f"Recent traceback:\n{console_preview}")
        return 1

    # After generation, show summary
    success = result.get("success", False)
    project_path = result.get('project_path', 'unknown')

    if success:
        print("Success")
        print_success(f"Project located at: {project_path}")
        print_success(f"Elapsed time: {result.get('elapsed_time', 0):.2f}s")
    else:
        print_error("Project generation incomplete. Check logs above.")
        print_error(f"Location: {project_path}")

    return 0 if success else 1

def cmd_sandbox(args):
    """Configure CubeSandbox connection details."""
    from .config import set_sandbox_template, get_sandbox_config

    template_id = (getattr(args, "template_id", None) or "").strip()
    if not template_id:
        cfg = get_sandbox_config()
        print("Current CubeSandbox configuration:")
        print(f"  template_id: {cfg.get('template_id') or '(unset)'}")
        print(f"  api_url    : {cfg.get('api_url')}")
        print(f"  api_key    : {cfg.get('api_key')}")
        print(
            "\nProvide --template-id <id> to update. "
            "Create a template with:\n"
            "  cubemastercli tpl create-from-image --image "
            "ccr.ccs.tencentyun.com/ags-image/sandbox-code:latest"
        )
        return 0

    api_url = getattr(args, "api_url", None) or None
    api_key = getattr(args, "api_key", None) or None
    ok = set_sandbox_template(template_id, api_url=api_url, api_key=api_key)
    if not ok:
        print("Failed to write sandbox config.")
        return 1
    print(f"Saved CubeSandbox template_id={template_id}.")
    if api_url:
        print(f"  api_url={api_url}")
    if api_key:
        print(f"  api_key={api_key}")
    return 0


def main():
    if "--json-rpc" in sys.argv[1:]:
        return cmd_json_rpc()

    # Check if running interactively (no arguments)
    if len(sys.argv) == 1:
        return interactive_mode()

    parser = argparse.ArgumentParser(
        prog="alphastack",
        description="ALPHASTACK - AI-powered project generator with sandboxed testing"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    gen_parser = subparsers.add_parser("generate", help="Generate a new project")
    gen_parser.add_argument("prompt", nargs="?", help="Project description")
    gen_parser.add_argument("-o", "--output", help="Output directory (default: ./created_projects)")
    gen_parser.add_argument("-p", "--provider", choices=["google", "openai", "vllm", "openrouter", "prime_intellect"],
                            help="Inference provider (default: from providers.json)")
    gen_parser.add_argument("-l", "--language", choices=["cuda", "others"],
                            help="Problem language profile: cuda or others (default: asks interactively)")
    gen_parser.set_defaults(func=cmd_generate)

    list_parser = subparsers.add_parser("list", help="List generated projects")
    list_parser.add_argument("-o", "--output", help="Projects directory (default: ./created_projects)")
    list_parser.set_defaults(func=cmd_list)

    clean_parser = subparsers.add_parser("clean", help="Remove generated projects")
    clean_parser.add_argument("-o", "--output", help="Projects directory (default: ./created_projects)")
    clean_parser.add_argument("-f", "--force", action="store_true", help="Skip confirmation")
    clean_parser.set_defaults(func=cmd_clean)

    setup_parser = subparsers.add_parser("setup", help="Configure API Keys")
    setup_parser.set_defaults(func=cmd_setup)

    blueprint_smoke_parser = subparsers.add_parser(
        "blueprint-smoke",
        help="Run only software blueprint generation (smoke test)"
    )
    blueprint_smoke_parser.add_argument("prompt", nargs="?", help="Project description")
    blueprint_smoke_parser.add_argument(
        "-p", "--provider",
        choices=["google", "openai", "vllm", "openrouter", "prime_intellect"],
        help="Inference provider (default: vllm)"
    )
    blueprint_smoke_parser.add_argument(
        "-l", "--language",
        choices=["cuda", "others"],
        help="Problem language profile: cuda or others (default: others)"
    )
    blueprint_smoke_parser.set_defaults(func=cmd_blueprint_smoke)

    sandbox_parser = subparsers.add_parser(
        "sandbox",
        help="Configure CubeSandbox connection (template_id, api_url, api_key)"
    )
    sandbox_parser.add_argument("--template-id", dest="template_id",
                                help="CubeSandbox template id (created via cubemastercli tpl create-from-image)")
    sandbox_parser.add_argument("--api-url", dest="api_url",
                                help="CubeSandbox API URL (default: http://127.0.0.1:3000)")
    sandbox_parser.add_argument("--api-key", dest="api_key",
                                help="CubeSandbox API key (default: dummy)")
    sandbox_parser.set_defaults(func=cmd_sandbox)

    args = parser.parse_args()

    if not args.command:
        # This should theoretically be unreachable due to the sys.argv check above,
        # but good for safety if main() is called differently.
        return interactive_mode()

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
