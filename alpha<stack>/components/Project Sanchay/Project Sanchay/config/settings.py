import os
import sys
import importlib.util
import logging
from typing import Any, Dict, Optional, List

# Load environment variables from .env file at the very beginning.
# This ensures environment variables are available when the settings are loaded.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv might not be installed in all environments (e.g., in a final bundled app
    # where all necessary environment variables are already set).
    # Log a warning but don't fail if it's missing.
    pass

# Initialize a basic logger for internal settings loading messages.
# A full, more sophisticated logging setup will be applied later once LOG_LEVEL is determined
# from the loaded settings.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Settings:
    """
    Manages application configuration. It loads default settings, applies
    environment-specific overrides, and then allows further overrides from
    environment variables. It implements a singleton pattern to ensure a
    single, consistent configuration object throughout the application.
    """

    _instance: Optional["Settings"] = None
    _config: Dict[str, Any]

    def __new__(cls) -> "Settings":
        """
        Ensures that only a single instance of the Settings class is created
        and used across the application (Singleton pattern).
        """
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._initialize()  # Initialize the new instance
        return cls._instance

    def _initialize(self) -> None:
        """
        Loads and merges configuration settings from various sources.
        Order of precedence (later overrides earlier):
        1. Default settings (`default.py`)
        2. Environment-specific settings (`development.py`, `production.py`, etc.)
        3. Explicit environment variables (e.g., `DATABASE_PATH` or `SANCHAY_DATABASE_PATH`)
        """
        self._config = {}
        self.BASE_DIR = self._find_project_root()
        self.APP_ENV = os.getenv("APP_ENV", "development").lower()
        logger.info(f"Initializing settings for environment: '{self.APP_ENV}'")

        # 1. Load default settings from 'default.py'
        default_config_path = os.path.join(self.BASE_DIR, "config", "default.py")
        if not os.path.exists(default_config_path):
            raise FileNotFoundError(f"Default configuration file not found at: {default_config_path}")
        self._load_config_from_file(default_config_path)

        # 2. Load environment-specific settings (e.g., 'development.py', 'production.py')
        env_config_filename = f"{self.APP_ENV}.py"
        env_config_path = os.path.join(self.BASE_DIR, "config", env_config_filename)
        if os.path.exists(env_config_path):
            logger.info(f"Loading environment-specific configuration from: {env_config_path}")
            self._load_config_from_file(env_config_path)
        else:
            logger.warning(
                f"No environment-specific config file found for '{self.APP_ENV}' at: {env_config_path}. "
                "Proceeding with default settings and environment variable overrides only."
            )

        # 3. Apply overrides from system environment variables
        self._apply_env_variable_overrides()

        # 4. Perform basic validation for critical settings
        self._validate_settings()

    def _find_project_root(self) -> str:
        """
        Traverses up the directory tree to find the project root, indicated by 'pyproject.toml'.
        This helps in locating configuration files reliably regardless of where the script is run.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Traverse up until we hit the filesystem root or find pyproject.toml
        while current_dir != os.path.dirname(current_dir):
            if os.path.exists(os.path.join(current_dir, "pyproject.toml")):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        logger.error(
            "Could not find 'pyproject.toml' in parent directories. "
            "Assuming the parent of the config directory as the project root. "
            "This may lead to incorrect path resolutions."
        )
        # Fallback: assume the project root is one level above the 'config' directory
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _load_config_from_file(self, file_path: str) -> None:
        """
        Loads settings from a specified Python file into the internal configuration dictionary.
        Only loads uppercase variables, following a common Python config convention.
        """
        # Create a unique module name to avoid conflicts if multiple config files are loaded
        module_name = f"sanchay_config_{os.path.basename(file_path).replace('.', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)

        if spec is None or spec.loader is None:
            logger.error(f"Could not create module spec or loader for {file_path}")
            return

        module = importlib.util.module_from_spec(spec)
        # Temporarily add to sys.modules to allow internal imports within config files
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            for key in dir(module):
                # Only consider uppercase attributes (convention for configuration variables)
                if key.isupper() and not key.startswith("_"):
                    self._config[key] = getattr(module, key)
            logger.debug(f"Successfully loaded settings from {file_path}")
        except Exception as e:
            logger.exception(f"Error loading configuration from {file_path}")
            raise  # Re-raise to halt execution if a config file is unreadable
        finally:
            # Clean up temporary module from sys.modules
            if module_name in sys.modules:
                del sys.modules[module_name]

    def _apply_env_variable_overrides(self) -> None:
        """
        Overrides configuration settings with values from environment variables.
        Environment variables can directly match a setting name (e.g., `DATABASE_PATH`)
        or be prefixed with `SANCHAY_` (e.g., `SANCHAY_DATABASE_PATH`).
        Attempts to convert environment variable string values to the appropriate type
        based on the existing setting's type.
        """
        for env_key, env_value in os.environ.items():
            setting_key = None
            if env_key in self._config:
                setting_key = env_key
            elif env_key.startswith("SANCHAY_"):
                # Allow prefixed environment variables to override
                potential_setting_key = env_key[len("SANCHAY_"):]
                if potential_setting_key in self._config:
                    setting_key = potential_setting_key
                elif potential_setting_key.isupper() and potential_setting_key not in self._config:
                    # Also allow adding new settings via prefixed env vars if they are uppercase
                    self._config[potential_setting_key] = env_value
                    logger.debug(f"Added new setting '{potential_setting_key}' from environment variable '{env_key}': '{env_value}'")
                    continue # Already handled this key

            if setting_key:
                original_value = self._config[setting_key]
                try:
                    # Attempt type conversion based on original setting's type
                    if isinstance(original_value, bool):
                        converted_value = env_value.lower() in ('true', '1', 't', 'y', 'yes')
                    elif isinstance(original_value, int):
                        converted_value = int(env_value)
                    elif isinstance(original_value, float):
                        converted_value = float(env_value)
                    elif isinstance(original_value, list):
                        # Simple comma-separated list parsing
                        converted_value = [item.strip() for item in env_value.split(',') if item.strip()]
                    else:  # Default to string
                        converted_value = env_value

                    if converted_value != original_value: # Only update if value actually changed
                        self._config[setting_key] = converted_value
                        logger.debug(f"Overridden setting '{setting_key}' with environment variable '{env_key}' value: '{converted_value}' (Type: {type(converted_value).__name__})")
                except ValueError as e:
                    logger.warning(
                        f"Could not convert environment variable '{env_key}' value '{env_value}' "
                        f"to type '{type(original_value).__name__}' for setting '{setting_key}': {e}. "
                        "Keeping original type or falling back to string."
                    )
                    # If conversion fails, keep the env_value as a string or original type based on preference.
                    # Here, we keep the env_value as a string if conversion failed.
                    self._config[setting_key] = env_value
                except Exception as e:
                    logger.warning(f"Unexpected error processing environment variable '{env_key}': {e}")

    def _validate_settings(self) -> None:
        """
        Performs basic validation on core application settings to ensure
        critical paths or values are present and well-formed.
        """
        # Example validation: Ensure DATABASE_PATH is set
        if not self._config.get("DATABASE_PATH"):
            logger.warning("DATABASE_PATH is not defined in the configuration. "
                           "The application might default to an in-memory database or fail.")

        # Example validation: Ensure LOG_LEVEL is a valid logging level
        log_level_str = self._config.get("LOG_LEVEL", "INFO").upper()
        if not hasattr(logging, log_level_str):
            logger.warning(f"Invalid LOG_LEVEL '{log_level_str}' found in settings. "
                           "Defaulting to INFO. Please use standard logging levels (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL).")
            self._config["LOG_LEVEL"] = "INFO" # Reset to a valid default

        # Add other critical validations here, e.g., for AWS credentials paths, etc.
        if self._config.get("AWS_ACCESS_KEY_ID") and not self._config.get("AWS_SECRET_ACCESS_KEY"):
            logger.warning("AWS_ACCESS_KEY_ID is set, but AWS_SECRET_ACCESS_KEY is missing. AWS S3 integration may fail.")


    def __getattr__(self, name: str) -> Any:
        """
        Provides direct attribute access to configuration settings
        (e.g., `settings.DATABASE_PATH`).
        """
        try:
            return self._config[name]
        except KeyError:
            raise AttributeError(f"Setting '{name}' not found in the application configuration.")

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Prevents direct modification of configuration settings after initialization,
        enforcing immutability for runtime consistency.
        Allows internal attributes (e.g., '_instance', '_config') to be set.
        """
        # Allow internal attributes specific to the Settings class to be set
        if name in ("_instance", "_config", "BASE_DIR", "APP_ENV"):
            super().__setattr__(name, value)
        # Allow methods of the class to be set during initialization or by the class itself
        elif name in dir(self.__class__) and callable(getattr(self.__class__, name)):
             super().__setattr__(name, value)
        elif hasattr(self, '_config') and name in self._config:
            # If the setting already exists, prevent modification outside of init
            raise TypeError(f"Configuration setting '{name}' is immutable after initialization. "
                            "Use environment variables to override settings.")
        else:
            # For new attributes or attributes not in _config during initialization
            super().__setattr__(name, value)


    def __repr__(self) -> str:
        """
        Provides a developer-friendly string representation of the Settings object.
        """
        return f"<Settings: environment='{self.APP_ENV}', base_dir='{self.BASE_DIR}'>"


# Create the singleton instance of Settings. This will trigger the configuration loading.
settings = Settings()

# After settings are loaded, re-configure the application's main logger
# with the LOG_LEVEL determined from the configuration.
try:
    # This import assumes that `src/sanchay_app/utils/logging_config.py` exists
    # and contains a `configure_logging` function.
    from src.sanchay_app.utils.logging_config import configure_logging
    configure_logging(log_level=settings.LOG_LEVEL)
    # Re-get the logger for this module to ensure it uses the newly configured settings
    logger = logging.getLogger(__name__)
    logger.debug("Application logging re-configured based on loaded settings.")
except ImportError:
    logger.warning("Could not import 'configure_logging' from 'src.sanchay_app.utils.logging_config'. "
                   "Full application logging might not be configured as expected.")
except AttributeError:
    logger.warning("LOG_LEVEL setting not found during logging re-configuration. "
                   "Using default log level from initial basicConfig.")
except Exception as e:
    logger.exception(f"An unexpected error occurred during logging configuration: {e}")

# This `settings` object is now ready to be imported and used throughout the application.
# Example usage: `from config.settings import settings`
# Then access values like `settings.DATABASE_PATH`, `settings.LOG_LEVEL`, etc.