"""Every prompt template must render without error."""

import pytest

from src.utils.prompt_manager import PromptManager


@pytest.fixture(scope="module")
def pm():
    return PromptManager()


def test_listing_templates(pm):
    templates = pm.list_templates()
    assert "planner_pipeline.j2" in templates
    assert "dockerfile_generation.j2" in templates
    assert "ping_greeting.j2" in templates


def test_ping_greeting_renders(pm):
    rendered = pm.render(
        "ping_greeting.j2",
        provider="openrouter",
        model="openai/gpt-oss-120b",
        description="an AI-powered project generator",
    )
    assert "alphastack" in rendered.lower()
    assert "openai/gpt-oss-120b" in rendered
    assert "openrouter" in rendered
    # Instructions to keep the response short and first-person.
    assert "first person" in rendered.lower() or "first-person" in rendered.lower()


def test_ping_greeting_without_description(pm):
    rendered = pm.render("ping_greeting.j2", provider="openai", model="gpt-4o")
    assert "alphastack" in rendered.lower()
    assert "gpt-4o" in rendered


def test_project_blueprint_renders(pm):
    rendered = pm.render_project_blueprint(
        user_prompt="a tiny CLI",
        system_info={"os": "linux"},
        architecture_content="## arch\ndetails",
    )
    assert "software_blueprint_details" in rendered
    assert "folder_structure" in rendered
    assert "file_formats" in rendered


def test_architecture_planning_renders(pm):
    rendered = pm.render_architecture_planning(
        user_prompt="a service",
        system_info={"os": "linux"},
    )
    assert rendered  # just needs to not crash


def test_missing_template_raises(pm):
    with pytest.raises(ValueError):
        pm.render("definitely_not_a_real_template_xyz.j2")
