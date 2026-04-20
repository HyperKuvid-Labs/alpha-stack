"""Shared fixtures for the alphastack test suite.

Key design: a `FakeProvider` class that's registered under dummy provider
names so blueprint/tool-call pipeline code can run without touching the
real network. Each test that needs deterministic LLM output injects the
next response into the provider's queue.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest


# ---------------------------------------------------------------------------
# Fake LLM provider
# ---------------------------------------------------------------------------

class FakeProvider:
    """Minimal stand-in for `InferenceProvider` used by tests.

    Register an instance via `InferenceManager._active_provider = FakeProvider(...)`
    and set `_active_provider_name` to a name that's in the registry (e.g.
    'openrouter'). The fake returns whatever you enqueued with `queue(...)`.
    """

    def __init__(self, model: str = "fake/fake-model"):
        self.config: Dict[str, Any] = {"model": model, "api_key": "fake-key"}
        self.total_tokens_used = 0
        self._responses: List[str] = []

    @property
    def model(self) -> str:
        return self.config.get("model", "")

    @property
    def api_key(self) -> Optional[str]:
        return self.config.get("api_key")

    def queue(self, text: str) -> "FakeProvider":
        self._responses.append(text)
        return self

    def queue_json(self, obj: Any) -> "FakeProvider":
        self._responses.append(json.dumps(obj))
        return self

    def get_client(self):
        # Most alphastack code paths go through `call_model`/`create_initial_message`.
        # When they do reach for `get_client()`, they call `.chat.completions.create`
        # or `.beta.chat.completions.parse`. We return a minimal shim.
        return _FakeClient(self)

    def create_initial_message(self, prompt: str) -> List[Dict[str, str]]:
        return [{"role": "user", "content": prompt}]

    def call_model(self, messages, tools=None, **kwargs):
        return self._next_response()

    def extract_text(self, response) -> str:
        return str(response)

    def format_tools(self, tool_definitions):
        return tool_definitions

    def extract_function_calls(self, response):
        return []

    def create_function_response(self, function_name, result, call_id=None):
        return {"role": "tool", "name": function_name, "content": json.dumps(result)}

    def accumulate_messages(self, messages, response, function_responses):
        messages.append({"role": "assistant", "content": str(response)})
        messages.extend(function_responses)

    def _next_response(self) -> str:
        if not self._responses:
            return ""
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, provider: FakeProvider):
        self._provider = provider
        self.chat = _FakeChatNamespace(provider)
        # Minimal `.beta.chat.completions.parse` stub — returns a shim whose
        # .choices[0].message.parsed is None so callers fall through to
        # plain chat completions.
        self.beta = _FakeBeta()


class _FakeBeta:
    def __init__(self):
        self.chat = _FakeBetaChat()


class _FakeBetaChat:
    def __init__(self):
        self.completions = _FakeBetaCompletions()


class _FakeBetaCompletions:
    def parse(self, *args, **kwargs):
        raise RuntimeError("fake provider: beta.parse unsupported (intentional)")


class _FakeChatNamespace:
    def __init__(self, provider: FakeProvider):
        self.completions = _FakeCompletions(provider)


class _FakeCompletions:
    def __init__(self, provider: FakeProvider):
        self._provider = provider

    def create(self, *args, **kwargs):
        content = self._provider._next_response()

        class _Msg:
            def __init__(self, c):
                self.content = c

        class _Choice:
            def __init__(self, c):
                self.message = _Msg(c)

        class _Completion:
            def __init__(self, c):
                self.choices = [_Choice(c)]

        return _Completion(content)


@pytest.fixture
def fake_provider(monkeypatch):
    """Wires a FakeProvider into InferenceManager and makes `initialize` /
    `reset` / `get_active_provider` return it. Also survives across
    `InferenceManager.reset()` calls inside the code under test (ping_model
    and generate_project both call reset+initialize).
    """
    from src.utils import inference
    from src.utils.inference import InferenceManager

    fp = FakeProvider()

    # Override class methods on InferenceManager so any path the code takes
    # ends up using the fake. Covers reset(), initialize(), get_active_provider(),
    # get_provider_config() (for key lookup).
    def _fake_initialize(provider_name=None, validate=True, model_override=None):
        if model_override:
            fp.config["model"] = model_override
        InferenceManager._active_provider = fp
        InferenceManager._active_provider_name = provider_name or "openrouter"
        return fp

    def _fake_reset():
        # Intentionally a no-op: keep the fake wired.
        pass

    def _fake_get_active():
        InferenceManager._active_provider = fp
        InferenceManager._active_provider_name = (
            InferenceManager._active_provider_name or "openrouter"
        )
        return fp

    monkeypatch.setattr(InferenceManager, "initialize", staticmethod(_fake_initialize))
    monkeypatch.setattr(InferenceManager, "reset", staticmethod(_fake_reset))
    monkeypatch.setattr(InferenceManager, "get_active_provider", staticmethod(_fake_get_active))

    InferenceManager._active_provider = fp
    InferenceManager._active_provider_name = "openrouter"

    yield fp

    # monkeypatch teardown restores attrs; also clear the singleton.
    InferenceManager._active_provider = None
    InferenceManager._active_provider_name = None


# ---------------------------------------------------------------------------
# Fixture project
# ---------------------------------------------------------------------------

@pytest.fixture
def mini_py_project(tmp_path_factory):
    """Writes a tiny 3-file python project to a temp dir and returns its path.

    Tree: src/a.py -> src/b.py -> src/c.py, plus `requests` external on a.py.
    """
    root = tmp_path_factory.mktemp("mini_py")
    src = root / "src"
    src.mkdir()
    (src / "a.py").write_text(
        "import requests\nfrom .b import foo\n\ndef handler():\n    return foo()\n"
    )
    (src / "b.py").write_text(
        "from .c import compute\n\ndef foo():\n    return compute()\n"
    )
    (src / "c.py").write_text(
        "import json\n\ndef compute():\n    return len(json.dumps({}))\n"
    )
    return str(root)


@pytest.fixture
def dep_analyzer(mini_py_project):
    """Returns a `DependencyAnalyzer` scanned over `mini_py_project` with no LLM.

    Uses `DGAT_DEPS_ONLY=1` so dgat runs the tree-sitter / regex extraction
    but skips description generation.
    """
    from src.utils.dependencies import DependencyAnalyzer, TreeNode
    from src.utils.inference import InferenceManager

    os.environ["DGAT_DEPS_ONLY"] = "1"
    # Force an active provider so the adapter can read config.
    InferenceManager._active_provider_name = "openrouter"

    da = DependencyAnalyzer()
    da.analyze_project_files(
        mini_py_project,
        folder_tree=TreeNode(Path(mini_py_project).name),
        folder_structure="src/",
    )
    return da


@pytest.fixture(autouse=True)
def _restore_env():
    """Snapshot and restore env vars each test touches."""
    snapshot = {k: os.environ.get(k) for k in list(os.environ.keys()) if k.endswith("_API_KEY") or k.startswith("DGAT_") or k.startswith("ALPHASTACK_")}
    yield
    # Restore
    for k, v in snapshot.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
