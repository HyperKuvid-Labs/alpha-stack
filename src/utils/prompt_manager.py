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

    def render_project_blueprint(self, user_prompt: Optional[str] = None, system_info: Optional[Dict[str, Any]] = None, problem_statement_language: str = "others") -> str:
        if problem_statement_language.lower() == "cuda":
            return self.render('project_blueprint_cuda.j2', user_prompt=user_prompt, system_info=system_info)
        return self.render('project_blueprint.j2', user_prompt=user_prompt, system_info=system_info)

    def render_folder_structure_extraction(
        self,
        user_prompt: Optional[str] = None,
        blueprint_payload: Optional[Dict[str, Any]] = None,
        raw_blueprint_output: Optional[str] = None,
    ) -> str:
        return self.render(
            'folder_structure_extraction.j2',
            user_prompt=user_prompt,
            blueprint_payload=blueprint_payload or {},
            raw_blueprint_output=raw_blueprint_output or "",
        )

    def render_file_generation(
        self,
        filepath: str,
        context: str,
        refined_prompt: str,
        tree: str,
        file_output_format: str,
        file_description: str
    ) -> str:
        return self.render(
            'file_generation.j2',
            filepath=filepath,
            context=context,
            refined_prompt=refined_prompt,
            tree=tree,
            file_output_format=file_output_format,
            file_description=file_description
        )

    def render_file_metadata(
            self,
            filepath: str,
            context: str,
            refined_prompt: str,
            tree: str,
            file_output_format: str,
            file_content: str
    ):
        return self.render(
            'metadata_generation.j2',
            filepath=filepath,
            context=context,
            refined_prompt=refined_prompt,
            tree=tree,
            file_output_format=file_output_format,
            file_content=file_content
        )

    def render_file_descriptor(
            self,
            software_blueprint,
            folder_structure,
            file_name
    ):
        return self.render(
            'file_descriptor.j2',
            software_bluprint_details=software_blueprint,
            folder_structure=folder_structure,
            file_name=file_name
        )

    def list_templates(self) -> list:
        return self.env.list_templates()
