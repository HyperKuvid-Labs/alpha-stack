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
