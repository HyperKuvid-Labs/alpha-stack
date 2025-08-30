import re
from typing import Optional

def clean_ai_generated_code(content: str, file_extension: Optional[str] = None) -> str:
    if not content:
        return content


    
    # Common programming languages and their used variants
    languages = [
        'python', 'py', 'javascript', 'js', 'typescript', 'ts', 'jsx', 'tsx',
        'java', 'kotlin', 'scala', 'go', 'rust', 'c', 'cpp', 'c++', 'csharp', 'cs',
        'php', 'ruby', 'swift', 'dart', 'r', 'matlab', 'perl', 'lua', 'haskell',
        'clojure', 'elixir', 'erlang', 'f#', 'fsharp', 'ocaml', 'scheme', 'racket',
        'sql', 'mysql', 'postgresql', 'sqlite', 'mongodb', 'redis',
        'html', 'css', 'scss', 'sass', 'less', 'xml', 'yaml', 'yml', 'json',
        'dockerfile', 'docker', 'bash', 'sh', 'zsh', 'fish', 'powershell', 'ps1',
        'makefile', 'cmake', 'gradle', 'maven', 'npm', 'yarn',
        'solidity', 'vyper', 'cairo', 'rust', 'move', 'clarity',
        'terraform', 'hcl', 'ansible', 'kubernetes', 'k8s'
    ]



    
    
    lang_pattern = '|'.join(re.escape(lang) for lang in languages)
    
    content = re.sub(rf'^```(?:{lang_pattern})?\s*\n?', '', content, flags=re.MULTILINE | re.IGNORECASE)
    content = re.sub(r'^```\s*$', '', content, flags=re.MULTILINE)
    
    content = re.sub(r'```(?:\w+)?', '', content)
    
    content = re.sub(r'^Here\'s.*?:\s*\n', '', content, flags=re.MULTILINE | re.IGNORECASE)
    content = re.sub(r'^This is.*?:\s*\n', '', content, flags=re.MULTILINE | re.IGNORECASE)
    content = re.sub(r'^The following.*?:\s*\n', '', content, flags=re.MULTILINE | re.IGNORECASE)
    
    content = re.sub(r'^#\s*filepath:\s*.*?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^//\s*filepath:\s*.*?\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^<!--\s*filepath:\s*.*?-->\n', '', content, flags=re.MULTILINE)
    
    content = _apply_language_specific_cleaning(content, file_extension)
    
    content = content.strip()
    
    if content and not content.endswith('\n'):
        content += '\n'
    
    return content




def _apply_language_specific_cleaning(content: str, file_extension: Optional[str]) -> str:
    
    if not file_extension:
        return content
    
    ext = file_extension.lower().lstrip('.')
    
    if ext in ['py']:
        lines = content.split('\n')
        seen_imports = set()
        cleaned_lines = []
        
        for line in lines:
            if line.strip().startswith(('import ', 'from ')):
                if line.strip() not in seen_imports:
                    seen_imports.add(line.strip())
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        content = '\n'.join(cleaned_lines)
    
    elif ext in ['js', 'jsx', 'ts', 'tsx']:
        content = re.sub(r'^(import\s+.*?;)\s*\n\1', r'\1', content, flags=re.MULTILINE)
        content = re.sub(r'^(const\s+.*?=\s*require\(.*?\);)\s*\n\1', r'\1', content, flags=re.MULTILINE)
    
    elif ext in ['java']:
        content = re.sub(r'^(package\s+.*?;)\s*\n\1', r'\1', content, flags=re.MULTILINE)
        content = re.sub(r'^(import\s+.*?;)\s*\n\1', r'\1', content, flags=re.MULTILINE)
    
    elif ext in ['sql']:
        content = re.sub(r';\s*;', ';', content)
    
    elif ext in ['html', 'htm']:
        content = re.sub(r'(<!DOCTYPE html>)\s*\n\1', r'\1', content, flags=re.IGNORECASE)

    elif ext in ['css', 'scss', 'sass']:
        content = re.sub(r'\s*\{\s*\}', '', content)
    
    elif ext in ['dockerfile'] or file_extension.lower() == 'dockerfile':
        from_statements = re.findall(r'^FROM\s+.*$', content, flags=re.MULTILINE)
        if len(from_statements) > 1:
            content = re.sub(r'^FROM\s+.*\n', '', content, flags=re.MULTILINE)
            content = from_statements[-1] + '\n' + content
    
    elif ext in ['yml', 'yaml']:
        content = re.sub(r'^---\s*\n---', '---', content, flags=re.MULTILINE)
    
    return content




def detect_language_from_content(content: str) -> Optional[str]:
    patterns = {
        'python': [r'def\s+\w+\(', r'import\s+\w+', r'from\s+\w+\s+import', r'if\s+__name__\s*==\s*["\']__main__["\']'],
        'javascript': [r'function\s+\w+\(', r'const\s+\w+\s*=', r'let\s+\w+\s*=', r'var\s+\w+\s*='],
        'typescript': [r'interface\s+\w+', r'type\s+\w+\s*=', r':\s*string', r':\s*number'],
        'java': [r'public\s+class\s+\w+', r'public\s+static\s+void\s+main', r'import\s+java\.'],
        'go': [r'func\s+\w+\(', r'package\s+main', r'import\s*\('],
        'rust': [r'fn\s+\w+\(', r'use\s+std::', r'let\s+mut\s+\w+'],
        'php': [r'<\?php', r'\$\w+\s*=', r'function\s+\w+\('],
        'ruby': [r'def\s+\w+', r'class\s+\w+', r'require\s+["\']'],
        'sql': [r'SELECT\s+', r'INSERT\s+INTO', r'CREATE\s+TABLE', r'ALTER\s+TABLE'],
        'html': [r'<html', r'<head>', r'<body>', r'<!DOCTYPE'],
        'css': [r'\w+\s*\{', r'@media', r'@import'],
        'dockerfile': [r'^FROM\s+', r'^RUN\s+', r'^COPY\s+', r'^ADD\s+'],
        'yaml': [r'^\w+:', r'^\s*-\s+\w+', r'---']
    }
    
    for lang, lang_patterns in patterns.items():
        for pattern in lang_patterns:
            if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                return lang
    
    return None
