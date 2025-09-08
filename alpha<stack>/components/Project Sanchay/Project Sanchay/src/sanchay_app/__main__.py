import sys
import os
import argparse
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QFile

# --- Custom Imports ---
# Attempt to import config.settings. If it fails, try to add the project root to sys.path.
# This ensures that 'config' can be imported when running from various contexts (e.g., as a script,
# or as part of a package).
try:
    from config.settings import get_settings
except ImportError:
    # Calculate project root dynamically relative to this __main__.py file.
    # __file__ is `project-sanchay/src/sanchay_app/__main__.py`
    # os.path.dirname(__file__) -> `project-sanchay/src/sanchay_app`
    # os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")) -> `project-sanchay/`
    project_root_for_import = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    sys.path.insert(0, project_root_for_import) # Add project root to Python's search path
    try:
        from config.settings import get_settings
    except ImportError as e:
        # If import still fails, log a critical error and exit.
        # A basic logger is needed here as the main setup_logging hasn't run yet.
        logging.basicConfig(level=logging.CRITICAL, format='%(levelname)s: %(message)s')
        logging.critical(f"CRITICAL ERROR: Could not import configuration module 'config.settings'.")
        logging.critical(f"Please ensure the project root '{project_root_for_import}' is in your PYTHONPATH, "
                         f"or that the 'config' package is correctly installed/accessible. Details: {e}")
        sys.exit(1)

# Relative imports for modules within the sanchay_app package
from .utils.logging_config import setup_logging
from .ui.main_window import MainWindow
from .cli import run_cli


# Initialize a logger for this module. Full logging setup happens later.
logger = logging.getLogger("sanchay")

def main():
    # Define PROJECT_ROOT again, as it's used for asset paths and should be consistent.
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    # 1. Load Application Configuration
    # `get_settings()` is expected to handle loading settings from various sources
    # (e.g., environment variables, default.py, development.py, production.py).
    settings = get_settings()

    # 2. Parse Command-Line Arguments
    parser = argparse.ArgumentParser(
        prog="sanchay", # Program name shown in help messages
        description="Project Sanchay: A file collection and processing application.\n\n"
                    "Run without arguments for GUI mode. Use --cli for command-line mode.",
        formatter_class=argparse.RawTextHelpFormatter # Preserves formatting in description
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the application in command-line interface mode.\n"
             "Further arguments after '--cli' will be parsed by the CLI module (e.g., 'sanchay --cli scan --path .')."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG logging level for verbose output.\n"
             "This flag overrides the 'LOG_LEVEL' setting from the configuration."
    )

    # `parse_known_args()` allows us to parse only top-level arguments here,
    # and pass the rest (e.g., CLI subcommands) to the CLI handler.
    args, unknown_args = parser.parse_known_args()

    # 3. Setup Application Logging
    # Convert string log level from settings to numeric level for the `logging` module.
    desired_log_level_str = "DEBUG" if args.debug else settings.LOG_LEVEL
    log_level_numeric = getattr(logging, desired_log_level_str.upper(), logging.INFO) # Robust conversion to numeric level
    
    # Pass log file path from settings, if available.
    log_file_path = None
    if hasattr(settings, 'LOG_FILE_PATH') and settings.LOG_FILE_PATH:
        # Ensure log directory exists before setting up the file handler.
        log_dir = os.path.dirname(settings.LOG_FILE_PATH)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        log_file_path = settings.LOG_FILE_PATH

    setup_logging(log_level_numeric, log_file_path=log_file_path)
    logger.info(f"Application starting with effective log level: {logging.getLevelName(log_level_numeric)}")
    logger.debug(f"Loaded settings: {settings.model_dump_json()}") # Assuming Pydantic v2 .model_dump_json()

    # 4. Launch Application Mode (GUI or CLI)
    if args.cli:
        logger.info("Launching Sanchay in CLI mode.")
        # The `run_cli` function in `cli.py` is responsible for parsing `unknown_args`
        # and executing the appropriate CLI commands.
        run_cli(unknown_args)
    else:
        logger.info("Launching Sanchay GUI.")
        app = QApplication(sys.argv)

        # Set application metadata for better OS integration (e.g., taskbar, about dialog).
        app.setApplicationName("Project Sanchay")
        app.setOrganizationName("Sanchay Team")
        app.setApplicationVersion(settings.APP_VERSION) # Assuming APP_VERSION is available in settings

        # Load and set application icon
        icon_path = os.path.join(PROJECT_ROOT, "assets", "icons", "app_icon.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            logger.debug(f"Loaded application icon from '{icon_path}'.")
        else:
            logger.warning(f"Application icon not found at '{icon_path}'. "
                           f"Ensure it is correctly bundled or accessible in the '{PROJECT_ROOT}/assets/icons/' directory.")

        # Load custom Qt Style Sheet (QSS) for UI theming
        style_path = os.path.join(PROJECT_ROOT, "assets", "styles", "main.qss")
        if os.path.exists(style_path):
            try:
                with open(style_path, "r", encoding="utf-8") as f:
                    app.setStyleSheet(f.read())
                logger.info(f"Loaded custom UI stylesheet from '{style_path}'.")
            except Exception as e:
                logger.error(f"Failed to load UI stylesheet from '{style_path}': {e}")
        else:
            logger.debug(f"No custom stylesheet found at '{style_path}'. Using default Qt styles.")

        # Create the main application window and pass the loaded settings.
        # The MainWindow will then use these settings to configure its components and dependencies.
        main_window = MainWindow(settings=settings)
        main_window.show()

        # Start the Qt event loop. This blocks until the application exits.
        exit_code = app.exec()
        logger.info(f"Sanchay GUI application exited with code {exit_code}.")
        sys.exit(exit_code)

if __name__ == "__main__":
    # If running `__main__.py` directly, ensure a basic logger is set up *before*
    # `main()` is called. This captures any critical errors during initial setup
    # (e.g., before `setup_logging` can configure full logging).
    if not logging.root.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        main()
    except Exception as e:
        logger.critical(f"An unhandled critical error occurred during Sanchay application startup or execution: {e}", exc_info=True)
        sys.exit(1)