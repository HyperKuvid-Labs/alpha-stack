import json
import os
from pathlib import Path

def get_providers():
    config_path = Path(__file__).resolve().with_name("providers.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Provider configuration file '{config_path}' not found.")
    with open(config_path, "r") as f:
        config = json.load(f)
    return config.get("model_providers", {})

if __name__ == "__main__":
    providers = get_providers()
    print("Available providers:", providers)