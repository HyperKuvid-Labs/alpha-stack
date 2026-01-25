
import os
import sys
import json
import time

# Add the project to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src_pi"))

# Import from src_pi modules (Prime Intellect version)
from src_pi.utils.prompt_manager import PromptManager
from src_pi.utils.helpers import prime_intellect_client
from src_pi.config import get_api_key_pi, set_api_key_pi

# ============================================================================
# CONFIGURATION
# ============================================================================

# Set your test prompt here
TEST_PROMPT = """rust based cli calculator"""

# Output directory for generated project
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")

# Set your Prime Intellect API key here (or use environment variable PRIME_API_KEY)
API_KEY = None  # Set to your key like "your-api-key-here" or leave None to use env/config

# Model configuration
MODEL_NAME = "z-ai/glm-4.7"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

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

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_test():
    print_header("ALPHASTACK TEST RUNNER (PRIME INTELLECT)")
    print(f"Model: {MODEL_NAME}")

    # Step 0: Check/Set API Key
    print_header("PHASE 0: PRIME INTELLECT API KEY CHECK")

    if API_KEY:
        os.environ["PRIME_API_KEY"] = API_KEY
        print(" Using API key from script configuration")
    elif get_api_key_pi():
        print(" Prime Intellect API key found in config/environment")
    else:
        print(" No Prime Intellect API key found!")
        print("   Set API_KEY in this script, or run: alphastack setup")
        print("   Or set environment variable: export PRIME_API_KEY='your-key'")
        return

    print(f"\n Test Prompt: {TEST_PROMPT}")
    print(f" Output Directory: {OUTPUT_DIR}")

    # Initialize prompt manager
    pm = PromptManager()

    start_time = time.time()

    # ========================================================================
    # PHASE 1: Software Blueprint
    # ========================================================================
    print_header("PHASE 1: SOFTWARE BLUEPRINT")
    print("Creating initial software blueprint from user prompt...")

    from src_pi.generator import initial_software_blueprint

    phase1_start = time.time()
    software_blueprint = initial_software_blueprint(TEST_PROMPT, pm)
    phase1_time = time.time() - phase1_start

    print_json(software_blueprint, "Software Blueprint Output")
    print(f"\n⏱️  Phase 1 completed in {phase1_time:.2f}s")

    if not software_blueprint:
        print(" Failed to create software blueprint!")
        return

    # ========================================================================
    # PHASE 2: Folder Structure
    # ========================================================================
    print_header("PHASE 2: FOLDER STRUCTURE")
    print("Generating folder structure from blueprint...")

    from src_pi.generator import folder_structure

    phase2_start = time.time()
    folder_struc = folder_structure(software_blueprint, pm)
    phase2_time = time.time() - phase2_start

    print_subheader("Folder Structure Output")
    print(folder_struc)
    print(f"\n  Phase 2 completed in {phase2_time:.2f}s")

    # ========================================================================
    # PHASE 3: File Format Contracts
    # ========================================================================
    print_header("PHASE 3: FILE FORMAT CONTRACTS")
    print("Creating file format contracts...")

    from src_pi.generator import files_format

    phase3_start = time.time()
    file_format = files_format(software_blueprint, folder_struc, pm)
    phase3_time = time.time() - phase3_start

    print_subheader("File Format Output")
    print(file_format)
    print(f"\n  Phase 3 completed in {phase3_time:.2f}s")

    # ========================================================================
    # PHASE 4: Generate Tree & Files
    # ========================================================================
    print_header("PHASE 4: GENERATE PROJECT TREE & FILES")
    print("Building project tree and generating all files...")

    from src_pi.generator import generate_tree, dfs_tree_and_gen

    from src_pi.utils.dependencies import DependencyAnalyzer

    phase4_start = time.time()

    folder_tree = generate_tree(folder_struc, project_name="")
    print(" Folder tree structure created")
    dependency_analyzer = DependencyAnalyzer()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_file_name = os.path.join(OUTPUT_DIR, "projects_metadata.json")
    metadata_dict = {}

    dfs_tree_and_gen(
        root=folder_tree,
        refined_prompt=software_blueprint,
        tree_structure=folder_struc,
        project_name="",
        current_path="",
        parent_context="",
        json_file_name=json_file_name,
        metadata_dict=metadata_dict,
        dependency_analyzer=dependency_analyzer,
        file_output_format=file_format,
        output_base_dir=OUTPUT_DIR,
        pm=pm,
        on_status=status_handler
    )
    print(" Project files generated")

    project_root_path = os.path.join(OUTPUT_DIR, folder_tree.value)
    phase4_time = time.time() - phase4_start

    print_subheader("Generated Project Tree")
    print(f"Root: {folder_tree.value}")
    print(f"Project Path: {project_root_path}")

    # List generated files
    if os.path.exists(project_root_path):
        print_subheader("Generated Files")
        for root, dirs, files in os.walk(project_root_path):
            level = root.replace(project_root_path, '').count(os.sep)
            indent = '  ' * level
            print(f"{indent}📁 {os.path.basename(root)}/")
            subindent = '  ' * (level + 1)
            for file in files:
                print(f"{subindent}📄 {file}")

    print(f"\n Phase 4 completed in {phase4_time:.2f}s")

    # ========================================================================
    # PHASE 5: Dependency Analysis
    # ========================================================================
    print_header("PHASE 5: DEPENDENCY ANALYSIS")
    print("Analyzing project dependencies...")

    phase5_start = time.time()
    dependency_analyzer.analyze_project_files(project_root_path, folder_tree=folder_tree, folder_structure=folder_struc)
    phase5_time = time.time() - phase5_start

    # Save metadata
    with open(json_file_name, 'w') as f:
        json.dump(metadata_dict, f, indent=4)

    print(f" Dependency analysis complete")
    print(f"\nPhase 5 completed in {phase5_time:.2f}s")

    # ========================================================================
    # PHASE 6: Docker & Test File Generation
    # ========================================================================
    print_header("PHASE 6: DOCKER & TEST FILE GENERATION")
    print("Generating Dockerfile and test files...")

    from src_pi.docker.generator import DockerTestFileGenerator

    # Parse file_format if it's a string
    try:
        if isinstance(file_format, str):
            file_output_format = json.loads(file_format)
        else:
            file_output_format = file_format
    except:
        file_output_format = {}

    phase6_start = time.time()

    try:
        test_gen = DockerTestFileGenerator(
            project_root=project_root_path,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            metadata_dict=metadata_dict,
            dependency_analyzer=dependency_analyzer,
            pm=pm,
            on_status=status_handler
        )

        test_gen_results = test_gen.generate_all()
        print_subheader("Docker Generation Results")
        print_json(test_gen_results)
    except Exception as e:
        print(f"  Docker generation error: {e}")

    phase6_time = time.time() - phase6_start
    print(f"\n Phase 6 completed in {phase6_time:.2f}s")

    # ========================================================================
    # PHASE 7: Dependency Resolution (Feedback Loop)
    # ========================================================================
    print_header("PHASE 7: DEPENDENCY RESOLUTION (FEEDBACK LOOP)")
    print("Running dependency resolution feedback loop...")

    from src_pi.utils.dependencies import DependencyFeedbackLoop
    from src_pi.utils.error_tracker import ErrorTracker

    phase7_start = time.time()

    error_tracker = ErrorTracker(project_root_path)

    try:
        feedback_loop = DependencyFeedbackLoop(
            dependency_analyzer=dependency_analyzer,
            project_root=project_root_path,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            pm=pm,
            error_tracker=error_tracker
        )
        dep_results = feedback_loop.run_feedback_loop()
    except Exception as e:
        print(f" Dependency resolution failed with exception: {e}")
        import traceback
        traceback.print_exc()
        dep_results = {"success": False, "error": str(e), "exception": True}

    phase7_time = time.time() - phase7_start

    print_subheader("Dependency Resolution Results")
    print_json(dep_results)
    print(f"\n Phase 7 completed in {phase7_time:.2f}s")

    # ========================================================================
    # PHASE 8: Docker Testing Pipeline
    # ========================================================================
    print_header("PHASE 8: DOCKER TESTING PIPELINE")
    print("Running Docker build and tests...")
    print("  Note: Docker must be running for this phase to succeed")

    from src_pi.docker.testing import run_docker_testing

    phase8_start = time.time()

    try:
        docker_results = run_docker_testing(
            project_root=project_root_path,
            software_blueprint=software_blueprint,
            folder_structure=folder_struc,
            file_output_format=file_output_format,
            pm=pm,
            error_tracker=error_tracker,
            dependency_analyzer=dependency_analyzer,
            on_status=status_handler
        )
    except Exception as e:
        print(f" Docker testing failed with exception: {e}")
        import traceback
        traceback.print_exc()
        docker_results = {"success": False, "error": str(e), "exception": True}

    phase8_time = time.time() - phase8_start

    print_subheader("Docker Testing Results")
    print_json(docker_results)
    print(f"\n Phase 8 completed in {phase8_time:.2f}s")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    total_time = time.time() - start_time

    print_header("SUMMARY")
    print(f" Project Location: {project_root_path}")
    print()
    print("  Phase Timings:")
    print(f"   Phase 1 (Blueprint):        {phase1_time:.2f}s")
    print(f"   Phase 2 (Folder Structure): {phase2_time:.2f}s")
    print(f"   Phase 3 (File Formats):     {phase3_time:.2f}s")
    print(f"   Phase 4 (File Generation):  {phase4_time:.2f}s")
    print(f"   Phase 5 (Dep Analysis):     {phase5_time:.2f}s")
    print(f"   Phase 6 (Docker Gen):       {phase6_time:.2f}s")
    print(f"   Phase 7 (Dep Resolution):   {phase7_time:.2f}s")
    print(f"   Phase 8 (Docker Testing):   {phase8_time:.2f}s")
    print(f"   ─────────────────────────────────")
    print(f"   TOTAL:                      {total_time:.2f}s")
    print()

    overall_success = dep_results.get("success", False) and docker_results.get("success", False)

    if overall_success:
        print(" PROJECT GENERATION: COMPLETE SUCCESS")
    else:
        print("  PROJECT GENERATION: COMPLETED WITH ISSUES")
        if not dep_results.get("success"):
            print("   - Dependency resolution had issues")
        if not docker_results.get("success"):
            print("   - Docker testing had issues")

    # ========================================================================
    # SAVE AND DISPLAY ERROR LOGS
    # ========================================================================
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
            print(f"\n Error {i+1}:")
            for key, value in err.items():
                if key != "timestamp":
                    print(f"   {key}: {value}")
    else:
        print("\n No errors recorded in error history")

    # Display change log (fixes attempted)
    if error_tracker.change_log:
        print_subheader(f"Change Log ({len(error_tracker.change_log)} changes/fixes attempted)")
        for i, change in enumerate(error_tracker.change_log):
            status_icon = "✅" if not change.get('error') else "🔧"
            print(f"\n{status_icon} Change {i+1}:")
            print(f"   File: {change.get('file', 'N/A')}")
            print(f"   Description: {change.get('change_description', 'N/A')}")
            if change.get('error'):
                print(f"   Error Fixed: {change.get('error')[:200]}...")
            if change.get('actions'):
                print(f"   Actions: {', '.join(change.get('actions', []))}")
    else:
        print("\n✅ No changes/fixes were needed")

    # Check for command logs
    command_log_path = os.path.join(project_root_path, ".alpha_stack", "command_logs.json")
    if os.path.exists(command_log_path):
        print(f"\n💾 Command logs available at: {command_log_path}")
        try:
            with open(command_log_path, 'r') as f:
                cmd_logs = json.load(f)
                commands = cmd_logs.get("commands", [])
                if commands:
                    print_subheader(f"Command Execution Summary ({len(commands)} commands)")
                    for i, cmd in enumerate(commands):
                        status = "✅" if cmd.get("success") else "❌"
                        print(f"\n{status} Command {i+1}: {cmd.get('command', 'N/A')}")
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

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    try:
        run_test()
    except KeyboardInterrupt:
        print("\n\n Test interrupted by user")
    except Exception as e:
        print(f"\n Error: {e}")
        import traceback
        traceback.print_exc()

