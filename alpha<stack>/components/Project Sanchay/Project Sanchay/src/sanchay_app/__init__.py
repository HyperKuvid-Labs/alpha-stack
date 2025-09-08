__version__ = "0.1.0"
APP_NAME = "Project Sanchay"

# This __init__.py primarily marks the 'sanchay_app' directory as a Python package.
# Key components and setup functions are typically imported directly by '__main__.py'
# or other modules rather than being re-exported here to avoid circular dependencies
# and keep the package structure clear.
#
# If a public API for 'sanchay_app' were to be defined, its core components
# would be explicitly imported and re-exported here using 'from .submodule import ClassOrFunction'.
# For instance:
# from .config.settings import load_config
# from .utils.logging_config import setup_logging
# from .core.job_manager import JobManager
#
# However, for an application's main package, direct imports from submodules
# are often preferred by the primary entry points like __main__.py.