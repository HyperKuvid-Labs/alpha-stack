"""InferenceManager: provider config, model override, registry."""

import json
import os

import pytest


def test_registry_has_expected_providers():
    from src.utils.inference import _PROVIDER_REGISTRY

    for name in ("google", "openai", "openrouter", "prime_intellect"):
        assert name in _PROVIDER_REGISTRY


def test_get_provider_config_reads_providers_json():
    from src.utils.inference import InferenceManager

    cfg = InferenceManager.get_provider_config("openrouter")
    assert cfg.get("base_url", "").startswith("https://")
    assert cfg.get("model")


def test_get_provider_config_env_var_wins(monkeypatch):
    from src.utils.inference import InferenceManager

    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    cfg = InferenceManager.get_provider_config("openrouter")
    assert cfg["api_key"] == "env-key"


def test_get_provider_config_falls_back_to_config_file(monkeypatch, tmp_path):
    """Key-stored-in-config path — the bug we fixed earlier."""
    from src.utils.inference import InferenceManager
    from src import config as ascfg

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(ascfg, "CONFIG_FILE", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps({"api_keys": {"openrouter": "from-file"}}))

    cfg = InferenceManager.get_provider_config("openrouter")
    assert cfg["api_key"] == "from-file"


def test_initialize_rejects_missing_key(monkeypatch, tmp_path):
    from src.utils.inference import InferenceManager
    from src import config as ascfg

    InferenceManager.reset()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(ascfg, "CONFIG_FILE", tmp_path / "config.json")
    (tmp_path / "config.json").write_text("{}")

    with pytest.raises(ValueError, match="API key not found"):
        InferenceManager.initialize("openrouter", validate=True)


def test_create_provider_applies_model_override(monkeypatch):
    from src.utils.inference import InferenceManager

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    prov = InferenceManager.create_provider("openrouter", model_override="anthropic/claude-3.5-sonnet")
    assert prov.config["model"] == "anthropic/claude-3.5-sonnet"


def test_initialize_cache_invalidates_on_model_change(monkeypatch):
    """Switching models should rebuild the active provider, not reuse the cached one."""
    from src.utils.inference import InferenceManager

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    InferenceManager.reset()

    p1 = InferenceManager.initialize("openrouter", validate=True, model_override="a/model-one")
    p2 = InferenceManager.initialize("openrouter", validate=True, model_override="b/model-two")
    assert p1.config["model"] == "a/model-one"
    assert p2.config["model"] == "b/model-two"
