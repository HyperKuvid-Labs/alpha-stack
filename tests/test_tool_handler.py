"""ToolHandler tool dispatching — covers all dgat-backed primary tools."""

import os

import pytest

from src.utils.tools import ToolHandler


@pytest.fixture
def handler(dep_analyzer):
    return ToolHandler(
        project_root=dep_analyzer.project_root,
        dependency_analyzer=dep_analyzer,
    )


def test_unknown_function(handler):
    r = handler.handle_function_call("nope_not_a_tool", {})
    assert "error" in r


def test_get_file_dependencies(handler):
    r = handler.handle_function_call("get_file_dependencies", {"file_path": "src/a.py"})
    assert r["success"]
    assert "src/b.py" in r["dependencies"]


def test_get_file_dependencies_with_descriptions(handler):
    r = handler.handle_function_call(
        "get_file_dependencies",
        {"file_path": "src/a.py", "include_descriptions": True},
    )
    assert r["success"]
    assert "descriptions" in r
    # deps-only mode: descriptions are empty strings, but the key is present
    assert set(r["descriptions"].keys()) == set(r["dependencies"])


def test_get_file_dependents(handler):
    r = handler.handle_function_call("get_file_dependents", {"file_path": "src/c.py"})
    assert r["success"]
    assert "src/b.py" in r["dependents"]


def test_get_file_description_returns_entry(handler):
    """Description may be empty in deps-only mode, but the tool should succeed."""
    r = handler.handle_function_call("get_file_description", {"file_path": "src/a.py"})
    assert r["success"]
    assert "description" in r


def test_get_file_description_missing_path(handler):
    r = handler.handle_function_call("get_file_description", {"file_path": "does/not/exist.py"})
    assert not r["success"]
    assert "no description" in r["error"]


def test_search_files_finds_by_name(handler):
    r = handler.handle_function_call("search_files", {"query": "a.py", "limit": 5})
    assert r["success"]
    paths = [x["rel_path"] for x in r["results"]]
    assert "src/a.py" in paths


def test_search_files_requires_query(handler):
    r = handler.handle_function_call("search_files", {"query": ""})
    assert "error" in r


def test_get_project_blueprint_empty_in_deps_only(handler):
    """deps-only skips LLM description gen → blueprint is empty. Expect a friendly error."""
    r = handler.handle_function_call("get_project_blueprint", {})
    # Either success with content or a clear no-blueprint error — both are acceptable
    # but we should never raise.
    assert "success" in r
    if not r["success"]:
        assert "error" in r


def test_missing_file_path_param(handler):
    r = handler.handle_function_call("get_file_dependencies", {})
    assert "error" in r
    assert "file_path" in r["error"]


def test_tool_without_analyzer_returns_error():
    handler = ToolHandler(project_root="/tmp", dependency_analyzer=None)
    r = handler.handle_function_call("get_file_description", {"file_path": "x.py"})
    assert "error" in r


def test_web_search_dispatches_and_caches(handler, monkeypatch):
    calls = {"n": 0}

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, q, **kw):
            calls["n"] += 1
            return [
                {"title": "t1", "href": "https://x/1", "body": "b1"},
                {"title": "t2", "href": "https://x/2", "body": "b2"},
            ]

    import src.utils.web_search as ws
    monkeypatch.setattr(ws, "_load_ddgs", lambda: FakeDDGS)

    r1 = handler.handle_function_call(
        "web_search", {"query": "asyncio", "max_results": 2}
    )
    assert r1["success"] and len(r1["results"]) == 2
    assert r1["results"][0] == {"title": "t1", "url": "https://x/1", "snippet": "b1"}
    assert r1["cached"] is False

    r2 = handler.handle_function_call(
        "web_search", {"query": "asyncio", "max_results": 2}
    )
    assert r2["cached"] is True
    assert calls["n"] == 1  # cache served it


def test_web_search_requires_query(handler):
    r = handler.handle_function_call("web_search", {"query": ""})
    assert "error" in r


def test_browse_url_falls_back_to_http(handler, monkeypatch):
    import src.utils.web_browse as wb

    monkeypatch.setattr(wb, "_load_bh_helpers", lambda: None)
    monkeypatch.setattr(wb, "_daemon_socket_present", lambda: False)

    class FakeResp:
        headers = {}

        def read(self):
            return (
                b"<html><head><title>T</title></head>"
                b"<body>hello <b>world</b></body></html>"
            )

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(wb, "_http_open", lambda url, timeout: FakeResp())

    r = handler.handle_function_call("browse_url", {"url": "https://x/p"})
    assert r["success"] and r["mode"] == "http"
    assert "hello world" in r["content"]
    assert r["title"] == "T"

    r2 = handler.handle_function_call("browse_url", {"url": "https://x/p"})
    assert r2.get("cached") is True


def test_browse_url_requires_url(handler):
    r = handler.handle_function_call("browse_url", {"url": ""})
    assert "error" in r


def test_mark_complete_rejected_without_any_shell_run(handler):
    result = handler.handle_function_call(
        "mark_complete",
        {"reason": "done", "runtime_verification": "ran python main.py add/list/summary, all exit 0"},
    )
    assert result["success"] is False
    assert "no shell commands" in result["error"]


def test_mark_complete_rejected_without_runtime_verification(handler):
    handler.last_test_output = "===== 11 passed in 0.25s ====="
    result = handler.handle_function_call("mark_complete", {"reason": "tests pass"})
    assert result["success"] is False
    assert "runtime verification" in result["error"].lower()
    assert handler.tests_passed is False


def test_mark_complete_accepts_with_runtime_verification(handler):
    handler.last_test_output = "===== 11 passed in 0.25s ====="
    result = handler.handle_function_call(
        "mark_complete",
        {
            "reason": "tests pass",
            "runtime_verification": (
                "Executed python main.py add --amount 5 --category food (exit 0, printed "
                "confirmation); python main.py summary --month 2026-07 printed the category table."
            ),
        },
    )
    assert result["success"] is True
    assert handler.tests_passed is True
