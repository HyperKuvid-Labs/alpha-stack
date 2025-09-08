#so this file is to generate the more modular folder structre from the tech stack and requirements md file

import os
import pathlib
import google.generativeai as genai

def generate_structure()->str:
    path = pathlib.Path(os.getcwd()) / "docs" / "tech_stack_reqs.md"
    with open(path, "r") as f:
        content = f.read()
    prompt = f"""
    You are a **senior software architect** and build-systems engineer.

    Objective  
    Generate a **complete, modular folder structure** that matches the project’s technology stack and requirements.

    Inputs  
    {content}   ← this it the full markdown from *tech_stack_reqs.md* here.

    Constraints  
    1. **Technology-Specific** – Reflect every major language, framework, and tool called out.  
    2. **Modular & Scalable** – Group related functionality; allow effortless future expansion.  
    3. **Industry Standards** – Follow established best practices for each technology.  
    4. **Environment Separation** – Distinct areas for development, testing, and production settings.  
    5. **Essential Directories** – The tree **must include**:  
    - Application Core  
    - Frontend Components  
    - Backend Services  
    - Database Layer  
    - Authentication & Authorization  
    - Configuration Management  
    - Testing Suite  
    - Documentation  
    - Deployment & DevOps  
    - Utilities & Helpers  
    - Static Assets (if applicable)  
    - External Integrations  

    Output Format  
    • Use **exactly 2 spaces** per nesting level.  
    • Start with a single top-level folder named **{{project-root}}/**.  
    • Use **ASCII tree glyphs** (`├──`, `└──`) for readability.  
    • End lines representing **files** with brief `# inline comments` (≤ 60 chars).  
    • Include file extensions, config files (`package.json`, `pyproject.toml`, etc.), and every required `__init__.py`.  
    • **Do NOT** add explanations, markdown fences, or extra commentary—return **only the tree**.

    Example (pattern only)  
    project-root/  
    src/  
        core/  
        __init__.py  
        models.py            # Pydantic models  
        services.py          # Business logic  
        api/  
        __init__.py  
        routes/  
            __init__.py  
            auth.py            # Auth endpoints  
    tests/  
        unit/  
        integration/  
    config/  
        settings.py            # Central settings  
        database.py            # DB connections  
    docs/  
        api/  
        user-guide/  

    Process Guidance (internal)  
    1. **Silently analyse** the tech stack and extract all tiers (frontend, backend, infra, etc.).  
    2. Plan the hierarchy, ensuring each constraint is satisfied.  
    3. Write the tree in the specified format.  
    4. Double-check: no missing essential directories, no stray text.

    Return the folder structure **now**.
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