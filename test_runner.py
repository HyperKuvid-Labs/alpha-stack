import os
import sys
import json
import time
import argparse

# Add the project to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

# Import from src modules (since source code is in src/)
from src.utils.prompt_manager import PromptManager
from src.utils.inference import InferenceManager
from src.config import get_api_key, set_api_key
from src.generator import generate_architecture_plan, generate_project_blueprint, generate_tree
from src.orchestrator import ParallelOrchestrator
from src.utils.dependencies import DependencyAnalyzer, build_dependency_graph_tree
from src.utils.error_tracker import ErrorTracker
from src.testing.testing import run_testing_pipeline

# 
# Set your test prompt here
TEST_PROMPT = """
A simple Python CLI tool named 'greeter' that:
- Takes a --name argument (default: "world") and prints "Hello, <name>!".
- Has a --shout flag that prints the greeting in uppercase.
- Exposes a small function greet(name: str, shout: bool=False) -> str in a module,
  and a console entry point.
- Uses argparse, no third-party dependencies.
- Include a couple of pytest unit tests for greet() covering default, custom name, and shout=True.
"""

# Output directory for generated projec"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")

# Set your API key here (or use environment variable)
API_KEY = (
    None  # Set to your key like "your-api-key-here" or leave None to use env/config
)

# Set provider: "google" or "openrouter" (defaults to providers.json default if None)
PROVIDER_NAME = (
    None  # Set to "google" or "openrouter", or None to use default from providers.json
)


def print_header(title):
    """Print a nicely formatted header."""
    print("\n" + "=" * 80)
    print(f"🔹 {title}")
    print("=" * 80 + "\n")


def print_subheader(title):
    """Print a subheader."""
    print(f"\n--- {title} ---\n")


def print_json(data, title=None):
    """Pretty print JSON data."""
    if title:
        print_subheader(title)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            print(data)
            return
    print(json.dumps(data, indent=2))


def status_handler(event_type, message, **kwargs):
    """Handle status updates from the generator."""
    icons = {
        "step": "",
        "progress": "",
        "success": "",
        "error": "",
        "warning": "",
    }
    icon = icons.get(event_type, "")
    print(f"{icon} {message}")


def run_test(provider_name_arg=None):
    print_header("ALPHASTACK TEST RUNNER")

    # Step 0: Check/Set API Key and Provider
    print_header("PHASE 0: CONFIGURATION CHECK")

    # Get provider (priority: command-line arg > PROVIDER_NAME > default from config)
    provider_name = (
        provider_name_arg or PROVIDER_NAME or InferenceManager.get_default_provider()
    )
    print(f" Provider: {provider_name}")

    # Set API key if provided in script
    if API_KEY:
        env_key = f"{provider_name.upper()}_API_KEY"
        os.environ[env_key] = API_KEY
        print(f" Using API key from script configuration ({env_key})")

    # Initialize provider once (validates API key, caches provider instance)
    try:
        provider = InferenceManager.initialize(provider_name, validate=True)
        model_name = provider.model
        print(f" Model: {model_name}")
        print(f" Provider initialized successfully")
    except ValueError as e:
        print(f" Error: {e}")
        return

    print(f"\n Test Prompt: {TEST_PROMPT}")
    print(f" Output Directory: {OUTPUT_DIR}")

    # Initialize prompt manager
    pm = PromptManager()

    start_time = time.time()
    
    # ==========================================
    # PHASE 1: ARCHITECTURE PLANNING
    # ==========================================
    print_header("PHASE 1: ARCHITECTURE PLANNING")
    print("Designing system architecture (components, data flows, interfaces)...")

    phase1_start = time.time()
    architecture_content = generate_architecture_plan(TEST_PROMPT, pm, provider_name)
    phase1_time = time.time() - phase1_start

    if not architecture_content:
        print(" Failed to generate architecture plan!")
        return

    # Save architecture doc to .alpha_stack/
    alpha_stack_dir = os.path.join(OUTPUT_DIR, ".alpha_stack")
    os.makedirs(alpha_stack_dir, exist_ok=True)
    arch_path = os.path.join(alpha_stack_dir, "architecture.md")
    with open(arch_path, "w") as f:
        f.write(architecture_content)
    print(f" Architecture document saved to: {arch_path}")
    print_subheader("Architecture Document")
    print(architecture_content)
    print(f"\n⏱️  Phase 1 completed in {phase1_time:.2f}s")

    # ==========================================
    # PHASE 2: COMPUTING PROJECT BLUEPRINT
    # ==========================================
    print_header("PHASE 2: COMPUTING PROJECT BLUEPRINT")
    print("Planning file structure and generating per-file contracts...")

    phase2_start = time.time()
    blueprint = generate_project_blueprint(TEST_PROMPT, pm, provider_name, architecture_content=architecture_content)
    phase2_time = time.time() - phase2_start

    if not blueprint:
        print(" Failed to compute software blueprint!")
        return

    # Extract parsed fields from Pydantic model
    software_blueprint = blueprint.software_blueprint_details
    folder_struc = blueprint.folder_structure
    file_format = blueprint.file_formats

    print_json(software_blueprint, "Software Blueprint Output")
    print_subheader("Folder Structure Output")
    print(folder_struc)
    print_subheader("File Format Output")
    print_json(file_format, "File Format Output")

    print(f"\n⏱️  Phase 2 completed in {phase2_time:.2f}s")


    # ==========================================
    # PHASE 3: GENERATE PROJECT TREE & FILES
    # ==========================================
    print_header("PHASE 3: GENERATE PROJECT TREE & FILES")
    print("Building project tree and generating all files...")

    phase3_start = time.time()

    folder_tree = generate_tree(folder_struc, project_name="")
    dependency_analyzer = DependencyAnalyzer()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Build the Parallel Orchestrator from the blueprint's file_format
    orchestrator = ParallelOrchestrator(output_base_dir=os.path.join(OUTPUT_DIR, folder_tree.value), max_workers=10)
    orchestrator.set_blueprint(software_blueprint, folder_struc, file_format)

    for filepath, details in file_format.items():
        prompt_rules = details.get("purpose", "")
        orchestrator.add_node(filepath, prompt_rules)

    orchestrator.execute()

    project_root_path = os.path.join(OUTPUT_DIR, folder_tree.value)
    error_tracker = ErrorTracker(project_root_path)
    phase3_time = time.time() - phase3_start

    print_subheader("Generated Project Tree")
    print(f"Root: {folder_tree.value}")
    print(f"Project Path: {project_root_path}")

    # List generated files
    if os.path.exists(project_root_path):
        print_subheader("Generated Files")
        for root, dirs, files in os.walk(project_root_path):
            level = root.replace(project_root_path, "").count(os.sep)
            indent = "  " * level
            print(f"{indent}📁 {os.path.basename(root)}/")
            subindent = "  " * (level + 1)
            for file in files:
                print(f"{subindent}📄 {file}")

    print(f"\n Phase 3 completed in {phase3_time:.2f}s")


    # ==========================================
    # PHASE 4: DEPENDENCY ANALYSIS
    # ==========================================
    print_header("PHASE 4: DEPENDENCY ANALYSIS")
    print("Analyzing project dependencies...")

    phase4_start = time.time()
    dependency_analyzer.analyze_project_files(
        project_root_path, folder_tree=folder_tree, folder_structure=folder_struc
    )
    phase4_time = time.time() - phase4_start

    print(" Dependency analysis complete")

    # Visualization of dependency graph
    dep_graph = build_dependency_graph_tree(project_root_path, dependency_analyzer)
    print("\nDependency Graph:\n" + dep_graph + "\n")

    print(f"\nPhase 4 completed in {phase4_time:.2f}s")


    # ==========================================
    # PHASE 5: TESTING PIPELINE
    # ==========================================
    print_header("PHASE 5: TESTING PIPELINE")
    print("Running tests (agent decides how based on project type)...")

    # Parse file_format if it's a string
    try:
        if isinstance(file_format, str):
            file_output_format = json.loads(file_format)
        else:
            file_output_format = file_format
    except:
        file_output_format = {}

    phase5_start = time.time()

    try:
        testing_results = run_testing_pipeline(
            project_root=project_root_path,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            pm=pm,
            error_tracker=error_tracker,
            dependency_analyzer=dependency_analyzer,
            on_status=status_handler,
            provider_name=provider_name,
        )
    except Exception as e:
        print(f" Testing pipeline failed with exception: {e}")
        import traceback

        traceback.print_exc()
        testing_results = {"success": False, "error": str(e), "exception": True}

    phase5_time = time.time() - phase5_start

    print_subheader("Testing Results")
    print_json(testing_results)
    print(f"\n Phase 5 completed in {phase5_time:.2f}s")
    total_time = time.time() - start_time

    print_header("SUMMARY")
    print(f" Project Location: {project_root_path}")
    print()
    print("  Phase Timings:")
    print(f"   Phase 1 (Architecture):         {phase1_time:.2f}s")
    print(f"   Phase 2 (Blueprint):            {phase2_time:.2f}s")
    print(f"   Phase 3 (File Generation):      {phase3_time:.2f}s")
    print(f"   Phase 4 (Dep Analysis):         {phase4_time:.2f}s")
    print(f"   Phase 5 (Testing Pipeline):     {phase5_time:.2f}s")
    print(f"   ─────────────────────────────────")
    print(f"   TOTAL:                          {total_time:.2f}s")
    print()

    overall_success = testing_results.get("success", False)

    if overall_success:
        print(" PROJECT GENERATION: COMPLETE SUCCESS")
    else:
        print("  PROJECT GENERATION: COMPLETED WITH ISSUES")
        if not testing_results.get("success"):
            print("   - Testing pipeline had issues")
    print_header("ERROR LOGS & DEBUG INFO")

    # Save error tracker to file
    error_log_path = os.path.join(OUTPUT_DIR, "error_tracker.json")
    try:
        error_tracker.save_to_file(error_log_path)
        print(f" Error tracker saved to: {error_log_path}")
    except Exception as e:
        print(f"  Could not save error tracker: {e}")

    # Display error history
    if error_tracker.error_history:
        print_subheader(f"Error History ({len(error_tracker.error_history)} errors)")
        for i, err in enumerate(error_tracker.error_history):
            print(f"\n Error {i + 1}:")
            for key, value in err.items():
                if key != "timestamp":
                    print(f"   {key}: {value}")
    else:
        print("\n No errors recorded in error history")

    # Display change log (fixes attempted)
    if error_tracker.change_log:
        print_subheader(
            f"Change Log ({len(error_tracker.change_log)} changes/fixes attempted)"
        )
        for i, change in enumerate(error_tracker.change_log):
            status_icon = "✅" if not change.get("error") else "🔧"
            print(f"\n{status_icon} Change {i + 1}:")
            print(f"   File: {change.get('file', 'N/A')}")
            print(f"   Description: {change.get('change_description', 'N/A')}")
            if change.get("error"):
                print(f"   Error Fixed: {str(change.get('error', ''))[:200]}...")
            if change.get("actions"):
                print(f"   Actions: {', '.join(change.get('actions', []))}")
    else:
        print("\n✅ No changes/fixes were needed")

    # Check for command logs
    command_log_path = os.path.join(
        project_root_path, ".alpha_stack", "command_logs.json"
    )
    if os.path.exists(command_log_path):
        print(f"\n💾 Command logs available at: {command_log_path}")
        try:
            with open(command_log_path, "r") as f:
                cmd_logs = json.load(f)
                commands = cmd_logs.get("commands", [])
                if commands:
                    print_subheader(
                        f"Command Execution Summary ({len(commands)} commands)"
                    )
                    for i, cmd in enumerate(commands):
                        status = "✅" if cmd.get("success") else "❌"
                        print(
                            f"\n{status} Command {i + 1}: {cmd.get('command', 'N/A')}"
                        )
                        print(f"   Exit Code: {cmd.get('returncode', 'N/A')}")
                        if not cmd.get("success") and cmd.get("logs"):
                            # Show last 500 chars of failed command logs
                            logs = cmd.get("logs", "")
                            print(f"   Error Output (last 500 chars):")
                            print(f"   {logs[-500:] if len(logs) > 500 else logs}")
        except Exception as e:
            print(f"   Could not read command logs: {e}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="AlphaStack Test Runner - Run the generator step-by-step",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_runner.py              # Uses default from providers.json
  python test_runner.py google       # Uses Google provider
  python test_runner.py openrouter  # Uses OpenRouter provider
        """,
    )
    parser.add_argument(
        "provider",
        nargs="?",
        default=None,
        choices=["google", "openai", "openrouter", "prime_intellect"],
        help="Provider name: 'google', 'openai', 'openrouter', or 'prime_intellect' (defaults to providers.json default if not specified)",
    )

    args = parser.parse_args()

    try:
        run_test(provider_name_arg=args.provider)
    except KeyboardInterrupt:
        print("\n\n Test interrupted by user")
    except Exception as e:
        print(f"\n Error: {e}")
        import traceback

        traceback.print_exc()
