#so this file is to generate the more modular folder structre from the tech stack and requirements md file

import os
import pathlib
import google.generativeai as genai

def generate_structure()->str:
    path = pathlib.Path(os.getcwd()) / "docs" / "tech_stack_reqs.md"
    with open(path, "r") as f:
        content = f.read()
    
    prompt = f"""
    Based on the following tech stack and requirements documentation, generate a comprehensive, modular folder structure for the application:

    {content}

    Requirements for the folder structure:
    1. **Technology-Specific Organization**: Structure should reflect the actual tech stack mentioned (e.g., React frontend, Node.js backend, Python services)
    2. **Modular Architecture**: Clear separation of concerns with logical grouping of related functionality
    3. **Scalability**: Structure should support future growth and feature additions
    4. **Industry Standards**: Follow best practices for the identified technology stack
    5. **Environment Configuration**: Include proper setup for development, testing, and production environments

    Include the following essential directories based on the tech stack:
    - **Application Core**: Main business logic and application entry points
    - **Frontend Components**: UI components, pages, assets, and styling (if applicable)
    - **Backend Services**: API routes, controllers, middleware, and business logic
    - **Database Layer**: Models, schemas, migrations, and database utilities
    - **Authentication & Authorization**: User management, auth middleware, and security
    - **Configuration Management**: Environment configs, settings, and constants
    - **Testing Suite**: Unit tests, integration tests, and test utilities
    - **Documentation**: API docs, user guides, and technical documentation
    - **Deployment & DevOps**: Docker files, CI/CD configs, and deployment scripts
    - **Utilities & Helpers**: Shared utilities, common functions, and helper modules
    - **Static Assets**: Images, fonts, and other static resources (if needed)
    - **External Integrations**: Third-party service integrations and API clients

    Output Format:
    - Use clear hierarchical indentation (2 spaces per level)
    - Include relevant file extensions and key files
    - Add brief inline comments for clarity where needed
    - Structure should be immediately implementable
    - Include __init__.py files for Python packages where appropriate
    - Show configuration files, package.json, requirements.txt, etc. as relevant

    Example structure format:
    project-root/
    src/
    core/
    init.py
    models.py
    services.py
    api/
    init.py
    routes/
    init.py
    auth.py
    users.py
    tests/
    unit/
    integration/
    config/
    settings.py
    database.py
    docs/
    api/
    user-guide/

    text

    Generate ONLY the folder structure - no additional explanations or text. And no comments besides the inline comments in the structure.
    """

    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents = prompt
    )

    path = pathlib.Path(os.getcwd()) / "docs" / "folder_structure.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(resp.text)
    print("Folder structure generated and saved to:", path)
    return resp.text