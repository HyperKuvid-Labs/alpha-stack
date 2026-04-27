import os
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import json
from typing import Dict, Any, Optional


def get_prompts_dir() -> str:
    """
    Finds the prompts directory, whether running from source or installed package.
    """
    # Method 1: Check relative to this file (works for both dev and installed)
    this_file = Path(__file__).resolve()
    package_dir = this_file.parent.parent  # alphastack/utils -> alphastack
    prompts_in_package = package_dir / "prompts"
    
    if prompts_in_package.exists():
        return str(prompts_in_package)
    
    # Method 2: Check current working directory (legacy dev mode)
    cwd_prompts = Path.cwd() / "prompts"
    if cwd_prompts.exists():
        return str(cwd_prompts)
    
    # Method 3: Check alphastack subdirectory of cwd
    cwd_alphastack_prompts = Path.cwd() / "alphastack" / "prompts"
    if cwd_alphastack_prompts.exists():
        return str(cwd_alphastack_prompts)
    
    # Fallback: return the expected path (will fail later with a clear error)
    return str(prompts_in_package)


class PromptManager:
    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            templates_dir = get_prompts_dir()
        
        self.templates_dir = templates_dir

        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        self.env.filters['json_dumps'] = lambda x: json.dumps(x, indent=2)
    
    def render(self, template_name: str, **kwargs) -> str:
        try:
            template = self.env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            raise ValueError(f"Error rendering template '{template_name}': {str(e)} (Search path: {self.templates_dir})")
    
    def render_architecture_planning(self, user_prompt: Optional[str] = None, system_info: Optional[Dict[str, Any]] = None, previous_attempt: Optional[str] = None, critique_issues: Optional[list] = None) -> str:
        return self.render('architecture_planning.j2', user_prompt=user_prompt, system_info=system_info, previous_attempt=previous_attempt, critique_issues=critique_issues)

    def render_project_blueprint(self, user_prompt: Optional[str] = None, system_info: Optional[Dict[str, Any]] = None, architecture_content: Optional[str] = None, previous_attempt: Optional[str] = None, critique_issues: Optional[list] = None) -> str:
        return self.render('project_blueprint.j2', user_prompt=user_prompt, system_info=system_info, architecture_content=architecture_content, previous_attempt=previous_attempt, critique_issues=critique_issues)

    def render_architecture_critic(self, user_prompt: str, architecture_content: str) -> str:
        return self.render('architecture_critic.j2', user_prompt=user_prompt, architecture_content=architecture_content)

    def render_blueprint_critic(self, architecture_content: str, folder_structure: str, file_formats_json: str) -> str:
        return self.render('blueprint_critic.j2', architecture_content=architecture_content, folder_structure=folder_structure, file_formats_json=file_formats_json)

    def render_test_critic(self, user_prompt: str, architecture_content: str, test_contracts_json: str) -> str:
        return self.render('test_critic.j2', user_prompt=user_prompt, architecture_content=architecture_content, test_contracts_json=test_contracts_json)
    
    def list_templates(self) -> list:
        return self.env.list_templates()
