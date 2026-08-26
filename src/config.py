import os
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

CONFIG_DIR = Path.home() / ".alphastack"
CONFIG_FILE = CONFIG_DIR / "config.json"


# Map alpha-stack provider names → dgat provider names.
# dgat only knows: vllm, ollama, openai, anthropic, openrouter.
_DGAT_PROVIDER_MAP = {
    "openrouter": "openrouter",
    "openai": "openai",
    "prime_intellect": "openai",   # OpenAI-compatible with a custom endpoint
    "google": "openrouter",         # google/gemini-* model routed via openrouter
}


def load_config() -> Dict[str, Any]:
    """Loads the user configuration from ~/.alphastack/config.json."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_config(config_data: Dict[str, Any]) -> bool:
    """Saves the configuration to ~/.alphastack/config.json."""
    if not CONFIG_DIR.exists():
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False

    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
        try:
            CONFIG_FILE.chmod(0o600)
        except OSError:
            pass
        return True
    except IOError:
        return False


def get_api_key() -> Optional[str]:
    """Legacy helper — returns the Google API key (env var wins)."""
    return get_provider_api_key("google")


def set_api_key(api_key: str) -> bool:
    """Legacy helper — sets the Google API key."""
    return set_provider_api_key("google", api_key)


def get_provider_api_key(provider: str) -> Optional[str]:
    """Return the API key for a provider. Order: env var → config file."""
    if not provider:
        return None
    env_key = f"{provider.upper()}_API_KEY"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val

    cfg = load_config()
    api_keys = cfg.get("api_keys", {})
    if isinstance(api_keys, dict) and api_keys.get(provider):
        return api_keys[provider]

    # Backward compat with the old flat `google_api_key` slot.
    if provider == "google" and cfg.get("google_api_key"):
        return cfg["google_api_key"]
    return None


def set_provider_api_key(provider: str, api_key: str) -> bool:
    """Persist a provider API key. Also syncs dgat's config so `dgat scan`
    and the bundled adapter both see the new key.
    """
    if not provider or not api_key:
        return False
    cfg = load_config()
    api_keys = cfg.get("api_keys") if isinstance(cfg.get("api_keys"), dict) else {}
    api_keys[provider] = api_key
    cfg["api_keys"] = api_keys
    if provider == "google":
        cfg["google_api_key"] = api_key
    ok = save_config(cfg)
    try:
        sync_dgat_config()
    except Exception:
        pass
    return ok


def _load_providers_json() -> Dict[str, Any]:
    path = Path(__file__).with_name("providers.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _map_alphastack_to_dgat(
    alphastack_provider: str,
    model_override: Optional[str] = None,
) -> Tuple[str, str, Optional[str]]:
    """Return (dgat_provider, endpoint, model) for an alpha-stack provider."""
    providers_json = _load_providers_json()
    cfg = (providers_json.get("model_providers") or {}).get(alphastack_provider, {})
    model = model_override or cfg.get("model")
    endpoint = cfg.get("base_url")

    dgat_provider = _DGAT_PROVIDER_MAP.get(alphastack_provider, "openai")

    if dgat_provider == "openrouter" and not endpoint:
        endpoint = "https://openrouter.ai/api/v1"
    if dgat_provider == "openai" and not endpoint:
        endpoint = "https://api.openai.com/v1"

    if alphastack_provider == "google" and dgat_provider == "openrouter" and not model_override:
        # Google proxied via OpenRouter; pick a sensible default when caller
        # didn't specify one.
        model = "google/gemini-2.5-pro"

    return dgat_provider, endpoint, model


def sync_dgat_config(
    active_provider: Optional[str] = None,
    model_override: Optional[str] = None,
) -> bool:
    """Write ~/.dgat/config.json to reflect alpha-stack's provider config.

    This mirrors the alpha-stack `default_provider` (or a caller-supplied
    override) and its API key/model/endpoint into dgat's own config so
    that `dgat scan`, `dgat describe`, and the DependencyAnalyzer adapter
    all talk to the same LLM alpha-stack is currently pointed at.

    Returns True on success, False if dgat isn't installed or config IO failed.
    """
    try:
        from dgat.config import DGATConfig, ProviderConfig, save_config as _dgat_save
    except ImportError:
        return False

    providers_json = _load_providers_json()
    if not active_provider:
        active_provider = providers_json.get("default_provider", "openrouter")

    dgat_provider, endpoint, model = _map_alphastack_to_dgat(
        active_provider, model_override=model_override
    )
    api_key = get_provider_api_key(active_provider)

    # For google → openrouter routing, fall back to the openrouter key if
    # google itself has no key set (the user may have keyed openrouter instead).
    if active_provider == "google" and not api_key:
        api_key = get_provider_api_key("openrouter")

    try:
        _dgat_save(
            DGATConfig(
                default_provider=dgat_provider,
                providers={
                    dgat_provider: ProviderConfig(
                        endpoint=endpoint,
                        api_key=api_key,
                        model=model,
                    ),
                },
            )
        )
        return True
    except Exception:
        return False
