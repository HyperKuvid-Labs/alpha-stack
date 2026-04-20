"""Config module: api key lookup, provider-to-dgat mapping, dgat sync.

All of these are pure / filesystem-local — no network.
"""

import json
import os
from pathlib import Path

import pytest


def test_get_provider_api_key_env_wins(monkeypatch, tmp_path):
    from src import config

    monkeypatch.setenv("OPENROUTER_API_KEY", "env-wins-key")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps({"api_keys": {"openrouter": "file-key"}}))
    assert config.get_provider_api_key("openrouter") == "env-wins-key"


def test_get_provider_api_key_config_file_fallback(monkeypatch, tmp_path):
    from src import config

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps({"api_keys": {"openrouter": "from-file"}}))
    assert config.get_provider_api_key("openrouter") == "from-file"


def test_get_provider_api_key_legacy_google_slot(monkeypatch, tmp_path):
    """Back-compat: old installs stored google key in `google_api_key` flat field."""
    from src import config

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps({"google_api_key": "legacy"}))
    assert config.get_provider_api_key("google") == "legacy"


def test_get_provider_api_key_none_when_missing(monkeypatch, tmp_path):
    from src import config

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    assert config.get_provider_api_key("openai") is None


def test_set_provider_api_key_persists(monkeypatch, tmp_path):
    from src import config

    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")

    ok = config.set_provider_api_key("openai", "sk-test-abc")
    assert ok

    stored = json.loads((tmp_path / "config.json").read_text())
    assert stored["api_keys"]["openai"] == "sk-test-abc"


def test_set_provider_api_key_rejects_empty(tmp_path, monkeypatch):
    from src import config

    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    assert not config.set_provider_api_key("", "x")
    assert not config.set_provider_api_key("openai", "")


@pytest.mark.parametrize(
    "alphastack_name, expected_dgat",
    [
        ("openrouter", "openrouter"),
        ("openai", "openai"),
        ("prime_intellect", "openai"),  # OpenAI-compatible endpoint
        ("google", "openrouter"),        # proxied via openrouter
    ],
)
def test_provider_mapping_to_dgat(alphastack_name, expected_dgat):
    from src.config import _map_alphastack_to_dgat

    dgat_prov, endpoint, model = _map_alphastack_to_dgat(alphastack_name)
    assert dgat_prov == expected_dgat
    assert endpoint
    assert isinstance(model, (str, type(None)))


def test_provider_mapping_honours_model_override():
    from src.config import _map_alphastack_to_dgat

    _, _, model = _map_alphastack_to_dgat("openrouter", model_override="anthropic/claude-3.5-sonnet")
    assert model == "anthropic/claude-3.5-sonnet"


def test_google_override_doesnt_force_default_model():
    """Previously google→openrouter always stamped gemini-2.5-pro; override must win."""
    from src.config import _map_alphastack_to_dgat

    _, _, model = _map_alphastack_to_dgat("google", model_override="google/gemini-3.1-flash-lite-preview")
    assert model == "google/gemini-3.1-flash-lite-preview"


def test_sync_dgat_config_writes_expected_shape(monkeypatch, tmp_path):
    from src import config

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-sync-test")
    dgat_cfg_path = tmp_path / ".dgat" / "config.json"

    # Redirect dgat's config path
    import dgat.config as dc

    monkeypatch.setattr(dc, "get_config_path", lambda: dgat_cfg_path)
    monkeypatch.setattr(dc, "get_config_dir", lambda: dgat_cfg_path.parent)
    dgat_cfg_path.parent.mkdir(parents=True, exist_ok=True)

    assert config.sync_dgat_config("openrouter")

    body = json.loads(dgat_cfg_path.read_text())
    assert body["default_provider"] == "openrouter"
    pc = body["providers"]["openrouter"]
    assert pc["api_key"] == "sk-sync-test"
    assert pc["endpoint"] == "https://openrouter.ai/api/v1"
    assert pc["model"]
