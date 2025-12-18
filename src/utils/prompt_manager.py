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
    
    def render_software_blueprint(self, user_prompt: Optional[str] = None) -> str:
        return self.render('software_blueprint.j2', user_prompt=user_prompt)
    
    def render_folder_structure(self, project_overview: Dict[str, Any]) -> str:
        return self.render('folder_structure.j2', project_overview=project_overview)
    
    def render_file_format(self, project_overview: Dict[str, Any], folder_structure: str) -> str:
        return self.render(
            'file_format.j2',
            project_overview=project_overview,
            folder_structure=folder_structure
        )
    
    def render_file_metadata(
        self,
        filename: str,
        file_type: str,
        context: str,
        refined_prompt: str,
        tree: str,
        file_content: str,
        file_output_format: str
    ) -> str:
        return self.render(
            'file_metadata.j2',
            filename=filename,
            file_type=file_type,
            context=context,
            refined_prompt=refined_prompt,
            tree=tree,
            file_content=file_content,
            file_output_format=file_output_format
        )
    
    def render_file_content(
        self,
        filename: str,
        file_type: str,
        context: str,
        refined_prompt: str,
        tree: str,
        file_output_format: str
    ) -> str:
        return self.render(
            'file_content.j2',
            filename=filename,
            file_type=file_type,
            context=context,
            refined_prompt=refined_prompt,
            tree=tree,
            file_output_format=file_output_format
        )
    
    def list_templates(self) -> list:
        return self.env.list_templates()
