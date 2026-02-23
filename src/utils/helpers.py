import os
import re
import json
import time
import platform
import sys
import subprocess
from typing import Dict, Any, List

SKIP_DIRS = {'__pycache__', '.git', '.vscode', '.idea', 'node_modules', '.pytest_cache'}


GENERATABLE_FILENAMES = {
    'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
    'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'tsconfig.json', 'jsconfig.json', 'next.config.js', 'next.config.mjs', 'babel.config.js', 'babel.config.json', 'postcss.config.js', 'tailwind.config.js', 'vite.config.js', 'vite.config.ts', 'webpack.config.js', 'webpack.config.ts', 'metro.config.js', 'metro.config.json',
    'requirements.txt', 'Pipfile', 'Pipfile.lock', 'pyproject.toml', 'setup.py', 'setup.cfg', 'manage.py', 'asgi.py', 'wsgi.py',
    'pom.xml', 'build.gradle', 'settings.gradle', 'gradlew', 'gradlew.bat', 'application.properties', 'application.yml', 'application.yaml',
    'composer.json', 'composer.lock', 'artisan', 'phpunit.xml',
    'Cargo.toml', 'Cargo.lock',
    'go.mod', 'go.sum', 'main.go',
    'Gemfile', 'Gemfile.lock', 'Rakefile',
    'mix.exs', 'mix.lock',
    'Program.cs', 'Startup.cs', 'appsettings.json',
    'Makefile', 'CMakeLists.txt',
    'Info.plist', 'Podfile', 'Podfile.lock', 'Cartfile', 'Cartfile.resolved',
    'build.gradle.kts', 'settings.gradle.kts', 'AndroidManifest.xml',
    'truffle-config.js', 'hardhat.config.js', 'foundry.toml', 'Anchor.toml',
    '.gitignore', '.gitattributes', '.env', '.env.example', '.editorconfig', '.prettierrc', '.prettierrc.js', '.prettierrc.json', '.eslintrc', '.eslintrc.js', '.eslintrc.json', '.eslintignore', '.stylelintrc', '.stylelintrc.json', '.lintstagedrc', '.huskyrc', '.flake8', '.pylintrc', '.pydocstyle', '.mypy.ini', '.github', '.github/workflows', '.gitlab-ci.yml', '.circleci/config.yml', 'Jenkinsfile', 'azure-pipelines.yml', '.travis.yml', '.appveyor.yml', 'netlify.toml', 'vercel.json','Procfile', 'Procfile.dev', 'Procfile.prod', 'now.json', 'firebase.json', 'manifest.json', 'robots.txt', 'sitemap.xml', 'index.html', 'index.js', 'index.ts', 'index.jsx', 'index.tsx'
}

GENERATABLE_FILES = {
    '.py', '.pyi',
    '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs',
    '.java', '.kt', '.kts', '.scala', '.groovy',
    '.php', '.phtml',
    '.rs',
    '.go',
    '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.cs', '.m', '.mm', '.swift',
    '.rb', '.ex', '.exs', '.erl',
    '.html', '.htm', '.xhtml', '.xml', '.svg', '.xsl',
    '.css', '.scss', '.sass', '.less', '.styl',
    '.json', '.yml', '.yaml', '.toml', '.ini', '.env', '.env.example',
    '.sh', '.bash', '.zsh', '.fish', '.bat', '.cmd', '.ps1', '.mk', '.make', '.cmake', '.gradle', '.mvn',
    '.md', '.rst', '.txt', '.adoc', '.asciidoc',
    '.sql', '.sqlite', '.db', '.migration',
    '.dockerfile', '.tf', '.hcl', '.circleci', '.gitlab-ci.yml', '.jenkins', '.travis.yml',
    '.sol', '.vy', '.cairo', '.move', '.clar',
    '.vue', '.svelte', '.dart', '.yaml', '.yml', '.json', '.tsx', '.jsx',
    '.lock', '.plist', '.conf', '.cfg', '.properties', '.pem', '.crt', '.csr', '.key', '.pub',
}




def build_project_structure_tree(project_root: str) -> str:
    lines = []

    def build_tree(dir_path, prefix="", is_last=True):
        rel_path = os.path.relpath(dir_path, project_root)
        if rel_path == '.':
            dir_name = os.path.basename(project_root)
        else:
            dir_name = os.path.basename(dir_path)

        if dir_name.startswith('.') and dir_name != '.':
            return

        connector = "└── " if is_last else "├── "
        lines.append(prefix + connector + dir_name + "/")

        prefix_add = "    " if is_last else "│   "
        new_prefix = prefix + prefix_add

        try:
            entries = sorted(os.listdir(dir_path))
            dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e)) and not e.startswith('.')]
            files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e)) and not e.startswith('.')]

            all_entries = dirs + files

            for i, entry in enumerate(all_entries):
                entry_path = os.path.join(dir_path, entry)
                is_last_entry = (i == len(all_entries) - 1)

                if os.path.isdir(entry_path):
                    build_tree(entry_path, new_prefix, is_last_entry)
                else:
                    connector = "└── " if is_last_entry else "├── "
                    lines.append(new_prefix + connector + entry)
        except PermissionError:
            pass

    try:
        build_tree(project_root)
    except Exception:
        pass

    return "\n".join(lines)





def clean_agent_output(content: str) -> str:
    if not content:
        return ""

    content = content.strip()

    if not content:
        return ""

    # Check for full markdown block spanning the content
    code_block_pattern = r'^```(?:[a-zA-Z0-9_\-\+]+)?\n(.*?)\n```$'
    match = re.match(code_block_pattern, content, re.DOTALL)
    if match:
        content = match.group(1).strip()
    else:
        # Fallback strip if it just starts and ends with ticks but doesn't perfectly match the regex
        if content.startswith('```'):
            lines = content.split('\n')
            if lines and lines[0].strip().startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            content = '\n'.join(lines).strip()

    content = content.rstrip('`').strip()

    if content and not content.endswith('\n'):
        content += '\n'

    return content




def get_system_info() -> Dict[str, Any]:
    system_info = {
        "operatingSystem": {
            "name": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "processor": platform.processor()
        },
        "environment": {
            "shell": os.environ.get("SHELL", "unknown"),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "home": os.environ.get("HOME", os.environ.get("USERPROFILE", "unknown"))
        }
    }
    return system_info
