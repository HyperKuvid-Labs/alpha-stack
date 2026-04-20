"""_rpc_ping_model uses the greeting prompt + live-ish call. Fake provider here."""

import json

import pytest


@pytest.fixture
def captured_emits(monkeypatch):
    """Hook cli._emit so we capture the payloads sent back to the TUI."""
    from src import cli

    out = []

    def fake_emit(req_id, type_, message="", data=None):
        out.append({"id": req_id, "type": type_, "message": message, "data": data})

    monkeypatch.setattr(cli, "_emit", fake_emit)
    return out


def test_ping_success_path(fake_provider, captured_emits):
    from src.cli import _rpc_ping_model

    fake_provider.queue("Ready and excited to generate code!")
    _rpc_ping_model({
        "id": "req-1",
        "params": {"provider": "openrouter", "model": "openai/gpt-oss-120b"},
    })

    result = [e for e in captured_emits if e["type"] == "result"][-1]
    assert result["data"]["ok"] is True
    assert "Ready" in result["data"]["message"]


def test_ping_empty_response_is_failure(fake_provider, captured_emits):
    from src.cli import _rpc_ping_model

    fake_provider.queue("")  # model returned nothing
    _rpc_ping_model({
        "id": "req-2",
        "params": {"provider": "openrouter", "model": "openai/gpt-oss-120b"},
    })
    result = [e for e in captured_emits if e["type"] == "result"][-1]
    assert result["data"]["ok"] is False
    assert "empty" in result["data"]["error"].lower()


def test_ping_missing_params_fails_fast(captured_emits):
    from src.cli import _rpc_ping_model

    _rpc_ping_model({"id": "req-3", "params": {"provider": "openrouter"}})
    result = [e for e in captured_emits if e["type"] == "result"][-1]
    assert result["data"]["ok"] is False
    assert "required" in result["data"]["error"]


def test_ping_greeting_template_reaches_provider(fake_provider, monkeypatch, captured_emits):
    """The greeting prompt must be passed to call_model verbatim (renders alphastack + model + provider)."""
    from src.cli import _rpc_ping_model

    seen_prompts = []
    orig_call = fake_provider.call_model

    def spy_call(messages, tools=None, **kw):
        seen_prompts.append(messages)
        return "ready"

    fake_provider.call_model = spy_call
    fake_provider.queue("ready")

    _rpc_ping_model({
        "id": "req-4",
        "params": {"provider": "openrouter", "model": "openai/gpt-oss-120b"},
    })

    assert seen_prompts, "call_model was not invoked"
    # greeting prompt is in the first (and only) user message
    greeting_text = seen_prompts[0][0]["content"]
    assert "alphastack" in greeting_text.lower()
    assert "openai/gpt-oss-120b" in greeting_text
    assert "openrouter" in greeting_text
