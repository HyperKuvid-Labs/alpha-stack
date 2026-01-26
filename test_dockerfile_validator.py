import os
import sys
import json

# Add the project to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from src.docker.validator import DockerfileValidator
from src.utils.prompt_manager import PromptManager

def test_validator():
    print("=" * 80)
    print("Testing DockerfileValidator")
    print("=" * 80)

    # Test on the number_adder_cli project
    test_project = os.path.join(project_root, "test_output", "number_adder_cli")

    if not os.path.exists(test_project):
        print(f"❌ Test project not found: {test_project}")
        return

    print(f"\n📁 Testing project: {test_project}\n")

    # Mock software blueprint
    software_blueprint = {
        "name": "CLI Number Adder",
        "description": "A command-line tool to add numbers",
        "language": "Python",
        "framework": "Click"
    }

    folder_structure = "cli_number_adder/"

    def status_handler(event_type, message, **kwargs):
        icons = {"step": "🔹", "progress": "⏳", "success": "✅", "error": "❌", "warning": "⚠️"}
        icon = icons.get(event_type, "ℹ️")
        print(f"{icon} {message}")

    pm = PromptManager()

    # Create validator
    try:
          validator = DockerfileValidator(
          project_root=test_project,
          software_blueprint=software_blueprint,
          folder_structure=folder_structure,
          pm=pm,
          on_status=status_handler
      )
    except Exception as e:
      print(f"\n❌ Failed to create DockerfileValidator: {e}")
      return


    # Run validation and fix
    print("\n" + "─" * 80)
    print("Running validation and fix...")
    print("─" * 80 + "\n")

    results = validator.validate_and_fix()

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(json.dumps(results, indent=2, default=str))

    if results.get('success'):
        print("\n✅ Validation/Fix completed successfully!")
        if results.get('fix', {}).get('modified'):
            print("   Dockerfile was modified to add test support")
            print(f"   Backup saved at: {results['fix']['backup_path']}")
    else:
        print("\n❌ Validation/Fix failed!")
        if 'error' in results:
            print(f"   Error: {results['error']}")

if __name__ == "__main__":
    try:
        test_validator()
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
