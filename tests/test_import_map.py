"""Deterministic path -> Python import-address mapping.

Regression guard for the loganalyze failure: files in a package imported
each other by bare module name ('from engine import X') because agents were
left to derive the address from the path. The mapping is now computed in
code and injected into agent context.
"""

import json

from src.generator import _build_prompt_rules
from src.utils.import_map import import_guidance, python_import_addresses


LOGANALYZE_PATHS = [
    "pyproject.toml",
    "loganalyze/__init__.py",
    "loganalyze/engine.py",
    "loganalyze/parser.py",
    "loganalyze/main.py",
    "tests/test_engine.py",
]


def test_addresses_from_paths():
    addrs = python_import_addresses(LOGANALYZE_PATHS)
    assert addrs["loganalyze/engine.py"] == "loganalyze.engine"
    assert addrs["loganalyze/__init__.py"] == "loganalyze"
    assert addrs["tests/test_engine.py"] == "tests.test_engine"
    assert "pyproject.toml" not in addrs


def test_top_level_module_address():
    assert python_import_addresses(["main.py"])["main.py"] == "main"


def test_guidance_gives_exact_import_forms():
    g = import_guidance("tests/test_engine.py", ["loganalyze/engine.py"], LOGANALYZE_PATHS)
    assert g["this_file_imports_as"] == "tests.test_engine"
    assert g["import_dependencies_exactly_as"]["loganalyze/engine.py"] == (
        "from loganalyze.engine import <name>"
    )
    assert "never" in g["rule"]


def test_guidance_empty_for_non_python():
    assert import_guidance("Cargo.toml", [], ["Cargo.toml", "src/main.rs"]) == {}


def test_prompt_rules_embed_import_guidance():
    details = {
        "purpose": "unit tests for the engine",
        "dependencies": ["loganalyze/engine.py"],
    }
    rules = _build_prompt_rules("tests/test_engine.py", details, all_paths=LOGANALYZE_PATHS)
    data = json.loads(rules)
    assert data["python_import_guidance"]["import_dependencies_exactly_as"][
        "loganalyze/engine.py"
    ].startswith("from loganalyze.engine import")
    # original contract fields untouched
    assert data["purpose"] == "unit tests for the engine"


def test_prompt_rules_unchanged_without_paths():
    details = {"purpose": "x", "dependencies": []}
    assert json.loads(_build_prompt_rules("a.py", details)) == details
