import re
from typing import Optional

def clean_ai_generated_code(text: str, ext: Optional[str] = None) -> str:
    if not text:
        return text
    
    # Common programming languages and their variants
    langs = [
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
    
    lang_re = '|'.join(re.escape(l) for l in langs)
    
    text = re.sub(rf'^```(?:{lang_re})?\s*\n?', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
    
    text = re.sub(r'```(?:\w+)?', '', text)
    
    text = re.sub(r'^Here\'s.*?:\s*\n', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^This is.*?:\s*\n', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^The following.*?:\s*\n', '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    text = re.sub(r'^#\s*filepath:\s*.*?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^//\s*filepath:\s*.*?\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^<!--\s*filepath:\s*.*?-->\n', '', text, flags=re.MULTILINE)
    
    text = _apply_lang_specific_cleaning(text, ext)
    
    text = text.strip()
    
    if text and not text.endswith('\n'):
        text += '\n'
    
    return text


def _apply_lang_specific_cleaning(text: str, ext: Optional[str]) -> str:
    if not ext:
        return text
    
    file_ext = ext.lower().lstrip('.')
    
    if file_ext in ['py']:
        lines = text.split('\n')
        seen = set()
        filtered = []
        
        for ln in lines:
            if ln.strip().startswith(('import ', 'from ')):
                if ln.strip() not in seen:
                    seen.add(ln.strip())
                    filtered.append(ln)
            else:
                filtered.append(ln)
        
        text = '\n'.join(filtered)
    
    elif file_ext in ['js', 'jsx', 'ts', 'tsx']:
        text = re.sub(r'^(import\s+.*?;)\s*\n\1', r'\1', text, flags=re.MULTILINE)
        text = re.sub(r'^(const\s+.*?=\s*require\(.*?\);)\s*\n\1', r'\1', text, flags=re.MULTILINE)
    
    elif file_ext in ['java']:
        text = re.sub(r'^(package\s+.*?;)\s*\n\1', r'\1', text, flags=re.MULTILINE)
        text = re.sub(r'^(import\s+.*?;)\s*\n\1', r'\1', text, flags=re.MULTILINE)
    
    elif file_ext in ['sql']:
        text = re.sub(r';\s*;', ';', text)
    
    elif file_ext in ['html', 'htm']:
        text = re.sub(r'(<!DOCTYPE html>)\s*\n\1', r'\1', text, flags=re.IGNORECASE)

    elif file_ext in ['css', 'scss', 'sass']:
        text = re.sub(r'\s*\{\s*\}', '', text)
    
    elif file_ext in ['dockerfile'] or ext.lower() == 'dockerfile':
        from_lines = re.findall(r'^FROM\s+.*$', text, flags=re.MULTILINE)
        if len(from_lines) > 1:
            text = re.sub(r'^FROM\s+.*\n', '', text, flags=re.MULTILINE)
            text = from_lines[-1] + '\n' + text
    
    elif file_ext in ['yml', 'yaml']:
        text = re.sub(r'^---\s*\n---', '---', text, flags=re.MULTILINE)
    
    return text


def detect_language_from_content(text: str) -> Optional[str]:
    lang_hints = {
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
    
    for lg, pats in lang_hints.items():
        for pat in pats:
            if re.search(pat, text, re.MULTILINE | re.IGNORECASE):
                return lg
    
    return None
