"""Adaptive two-pass blueprint: routing, fan-out assembly, and fallbacks.

The skeleton pass doubles as the complexity measurement — small projects keep
the single-pass blueprint, large ones fan contracts out per file. These tests
pin the routing decisions and failure handling without any LLM calls.
"""

import pytest

from src import generator
from src.generator import ProjectBlueprint, generate_project_blueprint_adaptive
from src.utils.prompt_manager import PromptManager


def _skeleton(n_files):
    files = {f"src/mod{i}.py": f"Module {i}, used by main.py" for i in range(n_files - 1)}
    files["main.py"] = "Entry point wiring all modules"
    return {
        "software_blueprint_details": {"name": "x", "version": "0.1", "summary": "s", "key_features": []},
        "folder_structure": "x/\n" + "\n".join(files),
        "files": files,
    }


def _contract_for(fp):
    return {
        "purpose": f"contract for {fp}",
        "behaviors": ["does a thing"],
        "interfaces": {"provides": []},
        "dependencies": [],
        "dependency_context": {},
        "test_contract": {},
        "external_packages": [],
    }


@pytest.fixture
def pm():
    return PromptManager()


def test_small_project_routes_to_single_pass(monkeypatch, pm):
    monkeypatch.setattr(generator, "generate_blueprint_skeleton", lambda *a, **k: _skeleton(4))
    sentinel = ProjectBlueprint(
        software_blueprint_details={}, folder_structure="tree", file_formats={"a.py": {}}
    )
    calls = {}

    def fake_single_pass(*a, **k):
        calls["single"] = True
        return sentinel

    monkeypatch.setattr(generator, "generate_project_blueprint", fake_single_pass)
    out = generate_project_blueprint_adaptive("p", pm)
    assert calls.get("single") and out is sentinel


def test_large_project_fans_out_per_file(monkeypatch, pm):
    skeleton = _skeleton(12)
    monkeypatch.setattr(generator, "generate_blueprint_skeleton", lambda *a, **k: skeleton)
    monkeypatch.setattr(
        generator, "generate_single_file_contract",
        lambda fp, purpose, sk, arch, pm: _contract_for(fp),
    )
    monkeypatch.setattr(
        generator, "generate_project_blueprint",
        lambda *a, **k: pytest.fail("single-pass must not run for large projects"),
    )
    out = generate_project_blueprint_adaptive("p", pm)
    assert isinstance(out, ProjectBlueprint)
    assert set(out.file_formats) == set(skeleton["files"])
    assert out.folder_structure == skeleton["folder_structure"]
    assert out.file_formats["main.py"]["purpose"] == "contract for main.py"


def test_skeleton_failure_falls_back_to_single_pass(monkeypatch, pm):
    monkeypatch.setattr(generator, "generate_blueprint_skeleton", lambda *a, **k: None)
    sentinel = ProjectBlueprint(
        software_blueprint_details={}, folder_structure="tree", file_formats={"a.py": {}}
    )
    monkeypatch.setattr(generator, "generate_project_blueprint", lambda *a, **k: sentinel)
    assert generate_project_blueprint_adaptive("p", pm) is sentinel


def test_failed_contract_becomes_stub_for_refinement(monkeypatch, pm):
    skeleton = _skeleton(12)
    monkeypatch.setattr(generator, "generate_blueprint_skeleton", lambda *a, **k: skeleton)

    def flaky(fp, purpose, sk, arch, pm):
        return None if fp == "src/mod3.py" else _contract_for(fp)

    monkeypatch.setattr(generator, "generate_single_file_contract", flaky)
    out = generate_project_blueprint_adaptive("p", pm)
    stub = out.file_formats["src/mod3.py"]
    # Stub keeps the skeleton purpose but omits required fields, so the
    # structural validator routes it into the refinement round.
    assert stub == {"purpose": skeleton["files"]["src/mod3.py"]}
    from src.utils.blueprint_validator import validate_blueprint
    issues = validate_blueprint(out.file_formats, out.folder_structure)
    assert any("src/mod3.py" in i and "missing required field" in i for i in issues)


def test_skeleton_prompt_renders(pm):
    rendered = pm.render(
        "blueprint_skeleton.j2",
        user_prompt="an app",
        system_info={"os": "test"},
        architecture_content="## arch",
    )
    assert "software_blueprint_details" in rendered
    assert "folder_structure" in rendered
    assert "files" in rendered


def test_file_contract_prompt_renders(pm):
    sk = _skeleton(3)
    rendered = pm.render(
        "file_contract.j2",
        filepath="main.py",
        file_purpose=sk["files"]["main.py"],
        architecture_content="## arch",
        folder_structure=sk["folder_structure"],
        files=sk["files"],
    )
    assert "main.py" in rendered
    assert "interfaces" in rendered
    assert "external_packages" in rendered
