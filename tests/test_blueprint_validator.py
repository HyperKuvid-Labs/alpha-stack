"""Structural blueprint validation — the code-enforced Phase 1 guards.

These rules exist in the blueprint prompt, but weak models drop them and
same-model critics don't catch it (observed: a flash-tier run planned one
integration test for a project whose prompt required unit tests per module).
The validator makes them model-independent.
"""

from src.utils.blueprint_validator import validate_blueprint


def _contract(deps=None):
    return {
        "purpose": "x",
        "behaviors": ["does x"],
        "interfaces": {"provides": []},
        "dependencies": deps or [],
        "external_packages": [],
        "test_contract": {},
    }


def _good_blueprint():
    return {
        "main.py": _contract(deps=["src/engine.py"]),
        "src/engine.py": _contract(deps=["src/storage.py"]),
        "src/storage.py": _contract(),
        "tests/test_engine.py": _contract(deps=["src/engine.py"]),
        "tests/test_storage.py": _contract(deps=["src/storage.py"]),
        "tests/test_integration.py": _contract(deps=["main.py"]),
        "requirements.txt": {"purpose": "deps", "behaviors": [], "external_packages": []},
    }


def _tree(paths):
    return "\n".join(paths)


def test_clean_blueprint_passes():
    bp = _good_blueprint()
    assert validate_blueprint(bp, _tree(bp)) == []


def test_module_without_unit_test_is_flagged():
    bp = _good_blueprint()
    del bp["tests/test_storage.py"]
    bp["src/engine.py"] = _contract(deps=["src/storage.py"])
    issues = validate_blueprint(bp, _tree(bp))
    assert any("storage.py" in i and "test" in i.lower() for i in issues)


def test_unwired_module_is_flagged():
    bp = _good_blueprint()
    bp["src/orphan.py"] = _contract()
    bp["tests/test_orphan.py"] = _contract(deps=["src/orphan.py"])
    issues = validate_blueprint(bp, _tree(bp))
    assert any("orphan.py" in i and "dependencies" in i for i in issues)


def test_missing_entry_point_is_flagged():
    bp = _good_blueprint()
    del bp["main.py"]
    del bp["tests/test_integration.py"]
    issues = validate_blueprint(bp, _tree(bp))
    assert any("entry point" in i.lower() for i in issues)


def test_dangling_dependency_path_is_flagged():
    bp = _good_blueprint()
    bp["src/engine.py"] = _contract(deps=["src/does_not_exist.py"])
    issues = validate_blueprint(bp, _tree(bp))
    assert any("does_not_exist.py" in i for i in issues)


def test_no_tests_at_all_is_flagged():
    bp = {
        "main.py": _contract(deps=["src/engine.py"]),
        "src/engine.py": _contract(),
    }
    issues = validate_blueprint(bp, _tree(bp))
    assert any("no test files" in i.lower() for i in issues)


def test_missing_integration_test_is_flagged():
    bp = _good_blueprint()
    del bp["tests/test_integration.py"]
    issues = validate_blueprint(bp, _tree(bp))
    assert any("integration" in i.lower() for i in issues)


def test_missing_contract_fields_flagged():
    bp = _good_blueprint()
    bp["src/engine.py"] = {"purpose": "x"}  # missing everything else
    issues = validate_blueprint(bp, _tree(bp))
    assert any("engine.py" in i and "missing required field" in i for i in issues)


def test_file_absent_from_tree_is_flagged():
    bp = _good_blueprint()
    tree_without_storage = _tree([p for p in bp if "storage" not in p])
    issues = validate_blueprint(bp, tree_without_storage)
    assert any("src/storage.py" in i and "folder_structure" in i for i in issues)


def test_spendlog_regression_shape():
    """The observed flash-tier failure: 5 source modules, one integration
    test, nothing else. Must produce unit-test issues for the modules."""
    bp = {
        "main.py": _contract(deps=["src/cli.py", "src/engine.py"]),
        "src/cli.py": _contract(),
        "src/engine.py": _contract(deps=["src/storage.py", "src/validator.py", "src/formatter.py"]),
        "src/storage.py": _contract(),
        "src/validator.py": _contract(),
        "src/formatter.py": _contract(),
        "tests/test_integration.py": _contract(deps=["main.py"]),
        "pyproject.toml": {"purpose": "deps", "behaviors": [], "external_packages": []},
    }
    issues = validate_blueprint(bp, _tree(bp))
    flagged = {m for m in ("cli", "engine", "storage", "validator", "formatter")
               if any(f"src/{m}.py" in i and "test" in i.lower() for i in issues)}
    # issues list is capped at 10, but several modules must be flagged
    assert len(flagged) >= 3, f"expected unit-test issues for modules, got: {issues}"
