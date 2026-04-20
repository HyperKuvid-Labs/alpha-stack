"""DependencyAnalyzer adapter: runs dgat in deps-only mode (no LLM)."""

import os

import pytest


def _abs(dep_analyzer, rel):
    return os.path.normpath(os.path.join(dep_analyzer.project_root, rel))


def test_graph_has_every_source_file(dep_analyzer):
    files = [_abs(dep_analyzer, "src/a.py"),
             _abs(dep_analyzer, "src/b.py"),
             _abs(dep_analyzer, "src/c.py")]
    for f in files:
        assert f in dep_analyzer.graph, f"missing node {f}"


def test_edge_a_to_b_present(dep_analyzer):
    a = _abs(dep_analyzer, "src/a.py")
    b = _abs(dep_analyzer, "src/b.py")
    assert dep_analyzer.graph.has_edge(a, b)


def test_edge_b_to_c_present(dep_analyzer):
    b = _abs(dep_analyzer, "src/b.py")
    c = _abs(dep_analyzer, "src/c.py")
    assert dep_analyzer.graph.has_edge(b, c)


def test_get_dependencies(dep_analyzer):
    a = _abs(dep_analyzer, "src/a.py")
    b = _abs(dep_analyzer, "src/b.py")
    deps = dep_analyzer.get_dependencies(a)
    assert b in deps


def test_get_dependents(dep_analyzer):
    b = _abs(dep_analyzer, "src/b.py")
    c = _abs(dep_analyzer, "src/c.py")
    a = _abs(dep_analyzer, "src/a.py")
    # b is depended-on-by a
    assert a in dep_analyzer.get_dependents(b)
    # c is depended-on-by b
    assert b in dep_analyzer.get_dependents(c)


def test_file_symbols_populated_by_tree_sitter(dep_analyzer):
    a = _abs(dep_analyzer, "src/a.py")
    syms = dep_analyzer.file_symbols.get(a, {})
    assert "handler" in syms.get("functions", [])


def test_external_packages_tracked(dep_analyzer):
    a = _abs(dep_analyzer, "src/a.py")
    details = dep_analyzer.get_dependency_details(a)
    externals = [d["raw"] for d in details if d.get("kind") == "external"]
    assert "requests" in externals


def test_build_dependency_graph_tree_render(dep_analyzer):
    from src.utils.dependencies import build_dependency_graph_tree

    tree = build_dependency_graph_tree(dep_analyzer.project_root, dep_analyzer)
    assert "a.py" in tree
    assert "deps:" in tree
    assert "used-by:" in tree or "dependents" not in tree  # sanity


def test_get_dependencies_empty_for_leaf(dep_analyzer):
    c = _abs(dep_analyzer, "src/c.py")
    # c.py imports only `json` (external) — no internal deps
    assert dep_analyzer.get_dependencies(c) == []


def test_get_dependents_empty_for_root(dep_analyzer):
    a = _abs(dep_analyzer, "src/a.py")
    # Nothing imports a.py
    assert dep_analyzer.get_dependents(a) == []
