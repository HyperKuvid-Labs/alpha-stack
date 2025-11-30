import os
import json
from pathlib import Path

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
    """Retrieves the Gemini API key from config or environment."""
    # First check environment variable
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return api_key
        
    # Then check config file
    config = load_config()
    return config.get("google_api_key")

def set_api_key(api_key):
    """Sets the Gemini API key in the config."""
    config = load_config()
    config["google_api_key"] = api_key
    return save_config(config)

