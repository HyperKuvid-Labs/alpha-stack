import os
import json
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".alphastack"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config():
    """Loads the user configuration from ~/.alphastack/config.json."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_config(config_data):
    """Saves the configuration to ~/.alphastack/config.json."""
    if not CONFIG_DIR.exists():
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False

    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)

        # Set permissions to be readable/writable only by the user (Unix)
        try:
            CONFIG_FILE.chmod(0o600)
        except OSError:
            pass

        return True
    except IOError:
        return False


def get_api_key():
    """Retrieves the Google API key from config or environment."""
    return get_provider_api_key("google")


def set_api_key(api_key):
    """Sets the Google API key in the config."""
    return set_provider_api_key("google", api_key)


def get_provider_api_key(provider_name: str) -> Optional[str]:
    """Retrieves the API key for a specific provider from config or environment."""
    env_var = f"{provider_name.upper()}_API_KEY"
    api_key = os.environ.get(env_var)
    if api_key:
        return api_key

    config = load_config()
    return config.get(f"{provider_name}_api_key")


def set_provider_api_key(provider_name: str, api_key: str) -> bool:
    """Sets the API key for a specific provider in the config."""
    config = load_config()
    config[f"{provider_name}_api_key"] = api_key
    return save_config(config)
