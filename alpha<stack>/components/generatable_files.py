# GENERATABLE_FILES = {
#     '.py', '.pyi', #python, django, flask, fastapi
#     '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', #for nodejs, mern, t3, react, next
#     '.java', '.kt', '.kts', '.scala', '.groovy', #springboot, kotlin, scala
#     '.php', '.phtml', #php, laravel
#     '.rs', # rust
#     '.go', #go
#     '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.cs', '.m', '.mm', '.swift', #c, cpp, objective-c, swift
#     '.rb', '.ex', '.exs', '.erl', #ruby, elixir, erlang
#     '.html', '.htm', '.xhtml', '.xml', '.svg', '.xsl', #html, xml
#     '.css', '.scss', '.sass', '.less', '.styl', #css
#     '.json', '.yml', '.yaml', '.toml', '.ini', '.env', '.env.example', #json, yaml
#     '.sh', '.bash', '.zsh', '.fish', '.bat', '.cmd', '.ps1', '.mk', '.make', '.cmake', '.gradle', '.mvn', #shell scripts, makefiles, gradle, maven
#     '.md', '.rst', '.txt', '.adoc', '.asciidoc', #markdown, text files
#     '.sql', '.sqlite', '.db', '.migration', #sql, database migrations
#     '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.bmp', '.tiff', '.avif', # Images
#     '.mp3', '.wav', '.ogg', '.mp4', '.mov', '.webm', #audio, video
#     '.dockerfile', '.tf', '.hcl', '.circleci', '.gitlab-ci.yml', '.jenkins', '.travis.yml', #docker, terraform, ci/cd
#     '.sol', '.vy', '.cairo', '.move', '.clar', #solidity, vyper, cairo, move, clarity
#     '.vue', '.svelte', '.dart', '.yaml', '.yml', '.json', '.tsx', '.jsx', #vue, svelte, dart
#     '.lock', '.plist', '.conf', '.cfg', '.properties', '.pem', '.crt', '.csr', '.key', '.pub', '.crt', '.csr', #extra web shit files
# }

# GENERATABLE_FILENAMES = {
#     'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
#     'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'tsconfig.json', 'jsconfig.json', 'next.config.js', 'next.config.mjs', 'babel.config.js', 'babel.config.json', 'postcss.config.js', 'tailwind.config.js', 'vite.config.js', 'vite.config.ts', 'webpack.config.js', 'webpack.config.ts', 'metro.config.js', 'metro.config.json',
#     'requirements.txt', 'Pipfile', 'Pipfile.lock', 'pyproject.toml', 'setup.py', 'setup.cfg', 'manage.py', 'asgi.py', 'wsgi.py',
#     'pom.xml', 'build.gradle', 'settings.gradle', 'gradlew', 'gradlew.bat', 'application.properties', 'application.yml', 'application.yaml',
#     'composer.json', 'composer.lock', 'artisan', 'phpunit.xml',
#     'Cargo.toml', 'Cargo.lock',
#     'go.mod', 'go.sum', 'main.go',
#     'Gemfile', 'Gemfile.lock', 'Rakefile',
#     'mix.exs', 'mix.lock',
#     'Program.cs', 'Startup.cs', 'appsettings.json',
#     'Makefile', 'CMakeLists.txt',
#     'Info.plist', 'Podfile', 'Podfile.lock', 'Cartfile', 'Cartfile.resolved',
#     'build.gradle.kts', 'settings.gradle.kts', 'AndroidManifest.xml',
#     'truffle-config.js', 'hardhat.config.js', 'foundry.toml', 'Anchor.toml',
#     '.gitignore', '.gitattributes', '.env', '.env.example', '.editorconfig', '.prettierrc', '.prettierrc.js', '.prettierrc.json', '.eslintrc', '.eslintrc.js', '.eslintrc.json', '.eslintignore', '.stylelintrc', '.stylelintrc.json', '.lintstagedrc', '.huskyrc', '.github', '.github/workflows', '.gitlab-ci.yml', '.circleci/config.yml', 'Jenkinsfile', 'azure-pipelines.yml', '.travis.yml', '.appveyor.yml', 'netlify.toml', 'vercel.json',
#     'README.md', 'README.rst', 'LICENSE', 'CONTRIBUTING.md', 'CHANGELOG.md', 'CODEOWNERS', 'SECURITY.md',
#     'Procfile', 'Procfile.dev', 'Procfile.prod', 'now.json', 'firebase.json', 'manifest.json', 'robots.txt', 'sitemap.xml', 'favicon.ico', 'index.html', 'index.js', 'index.ts', 'index.jsx', 'index.tsx'
# }

#so here i'm gonna define the function to decide upon the generatable files and folders
import pathlib
import os
import google.generativeai as genai

def get_gf(project_desc: str, folder_structure: str):
    # # Configure API
    # api_key = os.getenv("GEMINI_API_KEY")
    # if not api_key:
    #     raise ValueError("GEMINI_API_KEY environment variable not set")
    
    genai.configure(api_key="AIzaSyDqA_anmBc5of17-j2OOjy1_R6Fv_mwu5Y")

    prompt = f"""
    Based on the following project description and folder structure, determine the generatable files and filenames for the application:

    Project Description: {project_desc}
    Folder Structure: {folder_structure}

    Requirements for the generatable files and folders:
    Technology-Specific Files: Include files that are specific to the technologies mentioned in the project description (e.g., Python, Node.js, React, etc.)

    Modular Architecture: Ensure that the files and folders reflect a modular architecture with clear separation of concerns

    Scalability: The structure should support future growth and feature additions

    Industry Standards: Follow best practices for the identified technology stack

    Environment Configuration: Include proper setup for development, testing, and production environments

    Developer Experience: Include tooling configs, linting, formatting, and automation files

    Documentation: Include essential documentation files for the project

    Output Format:
    Return ONLY a valid JSON object with two arrays - no markdown code blocks, no explanations, no additional text. The response should start with {{ and end with }}:

    generatable_files: Array of file extensions that should be generated based on tech stack

    generatable_filenames: Array of specific filenames that are essential for the project

    Reference Extensions to Consider:
    .py, .pyi, .js, .jsx, .ts, .tsx, .mjs, .cjs, .java, .kt, .php, .rs, .go, .rb, .cs, .vue, .svelte, .html, .css, .scss, .sass, .less, .json, .yml, .yaml, .toml, .ini, .env, .sh, .bash, .md, .rst, .txt, .sql, .dockerfile, .tf, .hcl, .lock, .conf, .cfg, .properties

    Reference Filenames to Consider:
    Dockerfile, docker-compose.yml, package.json, package-lock.json, yarn.lock, requirements.txt, Pipfile, pyproject.toml, setup.py, manage.py, pom.xml, build.gradle, composer.json, Cargo.toml, go.mod, Gemfile, mix.exs, .gitignore, .env, .env.example, .prettierrc, .eslintrc, README.md, LICENSE, CONTRIBUTING.md, Procfile, manifest.json, index.html, index.js, tsconfig.json, next.config.js, vite.config.js, webpack.config.js

    Expected Output Format (return exactly in this structure):
    {{"generatable_files": [".js", ".jsx", ".ts", ".tsx", ".json", ".css", ".scss", ".md", ".env", ".yml", ".dockerfile"], "generatable_filenames": ["package.json", "package-lock.json", "tsconfig.json", "next.config.js", "tailwind.config.js", ".eslintrc.json", ".prettierrc", ".gitignore", ".env.example", "README.md", "Dockerfile", "docker-compose.yml", "vercel.json"]}}

    Note: Only include files relevant to the specified technology stack and ensure the generated structure supports team collaboration and deployment. Respond with raw JSON only.
    """

    resp = genai.GenerativeModel("gemini-2.5-pro-preview-05-06").generate_content(
        contents=prompt
    )

    response_text = resp.text.strip()
    
    if response_text.startswith('```json'):
        response_text = response_text[7:] #remove this first ```json`
    elif response_text.startswith('```'):
        response_text = response_text[3:]  #remove ````
    
    if response_text.endswith('```'):
        response_text = response_text[:-3]  # remove last ````
    
    response_text = response_text.strip()
    
    return response_text

def get_generatable_files():
    path = pathlib.Path(os.getcwd()) / "docs" / "tech_stack_reqs.md"
    if not path.exists():
        print("Tech stack and requirements documentation not found at:", path)
        return None
    with open(path, "r") as f:
        project_desc = f.read()

    path = pathlib.Path(os.getcwd()) / "docs" / "folder_structure.md"
    if not path.exists():
        print("Folder structure documentation not found at:", path)
        return None
    with open(path, "r") as f:
        folder_structure = f.read()

    gf = get_gf(project_desc, folder_structure)
    path = pathlib.Path(os.getcwd()) / "docs" / "generatable_files.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(gf)
    print(gf)
    return gf