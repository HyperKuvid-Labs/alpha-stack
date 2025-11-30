import argparse
import sys
import os


def status_handler(event_type, message, **kwargs):
    if event_type == "step":
        print(f"🔧 {message}")
    elif event_type == "progress":
        print(f"   {message}")
    elif event_type == "success":
        print(f"✅ {message}")
    elif event_type == "error":
        print(f"❌ {message}")
    elif event_type == "warning":
        print(f"⚠️  {message}")
    else:
        print(f"   {message}")


def cmd_generate(args):
    from .generator import generate_project
    
    print("=" * 80)
    print("🚀 ALPHASTACK - Project Generator")
    print("=" * 80)
    print()
    
    user_prompt = args.prompt
    output_dir = args.output or "./created_projects"
    
    if not user_prompt:
        user_prompt = input("Enter your project description: ").strip()
    
    if not user_prompt:
        print("❌ Project description is required!")
        return 1
    
    print(f"\n📝 Project: {user_prompt[:50]}...")
    print(f"📁 Output: {output_dir}")
    print()
    
    result = generate_project(user_prompt, output_dir, on_status=status_handler)
    
    if not result:
        print("\n❌ Project generation failed")
        return 1
    
    print("\n" + "=" * 80)
    print("📊 FINAL RESULTS")
    print("=" * 80)
    
    dep_result = result.get("dependency_resolution", {})
    docker_result = result.get("docker_testing", {})
    success = result.get("success", False)
    
    print(f"\n🔗 Dependency Resolution: {'✅ SUCCESS' if dep_result.get('success') else '❌ FAILED'}")
    if not dep_result.get('success'):
        remaining = dep_result.get("remaining_errors", [])
        if remaining:
            print(f"   {len(remaining)} remaining issues")
    
    print(f"\n🐳 Docker Build: {'✅ SUCCESS' if docker_result.get('build_success') else '❌ FAILED'}")
    if docker_result.get('build_success'):
        print(f"   Iterations: {docker_result.get('build_iterations', 0)}")
    
    print(f"\n🧪 Docker Tests: {'✅ SUCCESS' if docker_result.get('tests_success') else '❌ FAILED'}")
    if docker_result.get('tests_success'):
        print(f"   Iterations: {docker_result.get('test_iterations', 0)}")
    
    print(f"\n{'=' * 80}")
    if success:
        print("🎉 PROJECT GENERATION: COMPLETE SUCCESS")
        print("\n   ✅ All dependencies resolved")
        print("   ✅ Docker build successful")
        print("   ✅ All tests passed")
        print("\n   The project is ready to use!")
    else:
        print("⚠️  PROJECT GENERATION: INCOMPLETE")
        print("\n   Some steps may require manual fixes")
    
    print(f"\n⏱️  Time: {result.get('elapsed_time', 0):.2f}s")
    print(f"📁 Location: {result.get('project_path', 'unknown')}")
    print("=" * 80)
    
    return 0 if success else 1


def cmd_list(args):
    output_dir = args.output or "./created_projects"
    
    if not os.path.exists(output_dir):
        print(f"📁 No projects found in {output_dir}")
        return 0
    
    print(f"📁 Projects in {output_dir}:")
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
        dockerfile_exists = os.path.exists(os.path.join(project_path, "Dockerfile"))
        readme_exists = os.path.exists(os.path.join(project_path, "README.md"))
        
        status = "🐳" if dockerfile_exists else "📄"
        readme_status = "📖" if readme_exists else ""
        
        print(f"   {status} {project} {readme_status}")
    
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
                print(f"   ❌ Failed to delete {item}: {e}")
    
    print(f"\n✅ Deleted {deleted} project(s)")
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


def interactive_mode():
    """Launches the interactive TUI mode."""
    try:
        from .tui import display_logo, get_user_input, StatusDisplay, print_success, print_error
    except ImportError:
        # Fallback if dependencies are missing
        print("⚠️  TUI dependencies missing. Run 'pip install alphastack[tui]' or install rich, pyfiglet, prompt_toolkit.")
        # Create dummy args for generic flow
        dummy_args = argparse.Namespace(prompt=None, output=None)
        return cmd_generate(dummy_args)

    display_logo()
    
    try:
        user_prompt, output_dir = get_user_input()
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
        return 0
        
    from .generator import generate_project
    
    # Create status display
    status_display = StatusDisplay()
    
    def tui_status_handler(event_type, message, **kwargs):
        status_display.update(message, event_type)

    with status_display:
        result = generate_project(user_prompt, output_dir, on_status=tui_status_handler)

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


def main():
    # Check if running interactively (no arguments)
    if len(sys.argv) == 1:
        return interactive_mode()

    parser = argparse.ArgumentParser(
        prog="alphastack",
        description="ALPHASTACK - AI-powered project generator with Docker testing"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    gen_parser = subparsers.add_parser("generate", help="Generate a new project")
    gen_parser.add_argument("prompt", nargs="?", help="Project description")
    gen_parser.add_argument("-o", "--output", help="Output directory (default: ./created_projects)")
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
    
    args = parser.parse_args()
    
    if not args.command:
        # This should theoretically be unreachable due to the sys.argv check above,
        # but good for safety if main() is called differently.
        return interactive_mode()
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
