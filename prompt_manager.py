"""
Prompt Manager using Jinja2 for structured, maintainable prompting.
This module handles loading and rendering prompt templates.
"""
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import json
from typing import Dict, Any, Optional


class PromptManager:
    """Manages prompt templates using Jinja2"""
    
    def __init__(self, templates_dir: str = "prompts"):
        """
        Initialize the prompt manager with a templates directory.
        
        Args:
            templates_dir: Directory containing Jinja2 template files
        """
        self.templates_dir = templates_dir
        os.makedirs(templates_dir, exist_ok=True)
        
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        self.env.filters['json_dumps'] = lambda x: json.dumps(x, indent=2)
    
    def render(self, template_name: str, **kwargs) -> str:
        """
        Render a template with the given context variables.
        
        Args:
            template_name: Name of the template file (e.g., 'software_blueprint.j2')
            **kwargs: Context variables to pass to the template
            
        Returns:
            Rendered prompt string
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            raise ValueError(f"Error rendering template '{template_name}': {str(e)}")
    
    def render_software_blueprint(self, user_prompt: Optional[str] = None) -> str:
        """Render the software blueprint prompt"""
        return self.render('software_blueprint.j2', user_prompt=user_prompt)
    
    def render_folder_structure(self, project_overview: Dict[str, Any]) -> str:
        """Render the folder structure prompt"""
        return self.render('folder_structure.j2', project_overview=project_overview)
    
    def render_file_format(self, project_overview: Dict[str, Any], folder_structure: str) -> str:
        """Render the file format prompt"""
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
        """Render the file metadata generation prompt"""
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
        """Render the file content generation prompt"""
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
        """List all available templates"""
        return self.env.list_templates()

