from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    from tree_sitter_languages import get_language, get_parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

SUPPORTED_LANGUAGES: Dict[str, str] = {
    '.py': 'python', '.pyi': 'python',
    '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript',
    '.rs': 'rust',
    '.c': 'c', '.h': 'c',
    '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp',
    '.go': 'go',
}

@dataclass
class ImportInfo:
    """Represents a single import found in a source file."""
    raw: str             
    module: str           
    symbols: List[str] = field(default_factory=list) 


@dataclass
class ParseResult:
    """Result of parsing a single source file."""
    imports: List[ImportInfo] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    has_error: bool = False


def _text(node, source_bytes: bytes) -> str:
    """Extract UTF-8 text for an AST node."""
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def get_language_for_file(file_path: str) -> Optional[str]:
    """Return tree-sitter language name if the file extension is supported."""
    ext = Path(file_path).suffix.lower()
    return SUPPORTED_LANGUAGES.get(ext)

def _extract_python_imports(source_bytes: bytes, root_node) -> List[ImportInfo]:
    language = get_language("python")
    query = language.query("""
        (import_statement) @import_stmt
        (import_from_statement) @from_stmt
    """)
    captures = query.captures(root_node)
    seen: Set[tuple] = set()
    results: List[ImportInfo] = []

    for node, _ in captures:
        key = (node.start_byte, node.end_byte)
        if key in seen:
            continue
        seen.add(key)
        children = node.named_children
        if node.type == "import_statement":
            for child in children:
                if child.type == "dotted_name":
                    mod = _text(child, source_bytes)
                    results.append(ImportInfo(raw=mod, module=mod))
                elif child.type == "aliased_import":
                    for part in child.named_children:
                        if part.type == "dotted_name":
                            mod = _text(part, source_bytes)
                            results.append(ImportInfo(raw=mod, module=mod))
                            break
        elif node.type == "import_from_statement" and children:
            source_module = _text(children[0], source_bytes)
            symbols: List[str] = []
            for item in children[1:]:
                if item.type == "dotted_name":
                    symbols.append(_text(item, source_bytes))
                elif item.type == "aliased_import":
                    for part in item.named_children:
                        if part.type in ("dotted_name", "identifier"):
                            symbols.append(_text(part, source_bytes))
                            break
                elif item.type == "wildcard_import":
                    symbols.append("*")
            results.append(ImportInfo(
                raw=f"from {source_module} import {', '.join(symbols) if symbols else '*'}",
                module=source_module,
                symbols=symbols,
            ))

    return results

def _extract_js_family_imports(source_bytes: bytes, root_node, lang: str) -> List[ImportInfo]:
    language = get_language(lang)
    query = language.query("""
        (import_statement) @import_stmt
        (call_expression) @call_expr
    """)
    captures = query.captures(root_node)
    seen: Set[tuple] = set()
    results: List[ImportInfo] = []

    for node, _ in captures:
        key = (node.start_byte, node.end_byte)
        if key in seen:
            continue
        seen.add(key)

        if node.type == "import_statement":
            module_name = None
            symbols: List[str] = []
            for child in node.named_children:
                if child.type == "string":
                    module_name = _text(child, source_bytes).strip("\"'")
                elif child.type == "import_clause":
                    clause_text = _text(child, source_bytes).strip()
                    # Parse named imports: { a, b }
                    if "{" in clause_text:
                        inner = clause_text.split("{")[1].split("}")[0]
                        for sym in inner.split(","):
                            sym = sym.strip().split(" as ")[0].strip()
                            if sym:
                                symbols.append(sym)
                    else:
                        # Default import
                        default_name = clause_text.split(",")[0].strip()
                        if default_name and default_name != "*":
                            symbols.append(default_name)
            if module_name:
                results.append(ImportInfo(
                    raw=module_name,
                    module=module_name,
                    symbols=symbols,
                ))

        elif node.type == "call_expression":
            named = list(node.named_children)
            if len(named) < 2:
                continue
            callee = named[0]
            args = named[1]
            callee_text = _text(callee, source_bytes).strip()
            if callee.type != "import" and callee_text != "require":
                continue
            for arg in args.named_children:
                if arg.type == "string":
                    mod = _text(arg, source_bytes).strip("\"'")
                    label = "dynamic-import" if callee.type == "import" else "require"
                    results.append(ImportInfo(raw=mod, module=mod, symbols=[label]))
                    break

    return results
def _extract_rust_imports(source_bytes: bytes, root_node) -> List[ImportInfo]:
    language = get_language("rust")
    query = language.query("""
        (use_declaration) @use_stmt
        (extern_crate_declaration) @extern_stmt
        (mod_item) @mod_stmt
    """)
    captures = query.captures(root_node)
    seen: Set[tuple] = set()
    results: List[ImportInfo] = []

    for node, _ in captures:
        key = (node.start_byte, node.end_byte)
        if key in seen:
            continue
        seen.add(key)

        if node.type == "use_declaration":
            use_text = _text(node, source_bytes).strip().rstrip(";")
            # Remove "use " prefix
            if use_text.startswith("pub use "):
                use_path = use_text[8:].strip()
            elif use_text.startswith("use "):
                use_path = use_text[4:].strip()
            else:
                use_path = use_text
            # Extract top-level crate
            top_crate = use_path.split("::")[0].strip()
            results.append(ImportInfo(raw=use_path, module=top_crate))

        elif node.type == "extern_crate_declaration":
            for child in node.named_children:
                if child.type == "identifier":
                    name = _text(child, source_bytes)
                    results.append(ImportInfo(raw=name, module=name))
                    break

        elif node.type == "mod_item":
            has_body = any(c.type == "declaration_list" for c in node.named_children)
            if not has_body:
                for child in node.named_children:
                    if child.type == "identifier":
                        name = _text(child, source_bytes)
                        results.append(ImportInfo(raw=name, module=name))
                        break

    return results
def _extract_c_cpp_imports(source_bytes: bytes, root_node, lang: str) -> List[ImportInfo]:
    language = get_language(lang)
    query = language.query("(preproc_include) @include_stmt")
    captures = query.captures(root_node)
    seen: Set[tuple] = set()
    results: List[ImportInfo] = []

    for node, _ in captures:
        key = (node.start_byte, node.end_byte)
        if key in seen:
            continue
        seen.add(key)

        for child in node.named_children:
            if child.type == "system_lib_string":
                target = _text(child, source_bytes).strip("<>")
                results.append(ImportInfo(raw=target, module=target))
                break
            if child.type == "string_literal":
                target = _text(child, source_bytes).strip("\"")
                results.append(ImportInfo(raw=target, module=target))
                break

    return results
def _extract_go_imports(source_bytes: bytes, root_node) -> List[ImportInfo]:
    language = get_language("go")
    query = language.query("(import_declaration) @import_decl")
    captures = query.captures(root_node)
    seen: Set[tuple] = set()
    results: List[ImportInfo] = []

    def _add_spec(spec_node):
        alias = None
        path = None
        for child in spec_node.named_children:
            if child.type in ("package_identifier", "dot", "blank_identifier"):
                alias = _text(child, source_bytes)
            elif child.type == "interpreted_string_literal":
                path = _text(child, source_bytes).strip('"')
        if path:
            results.append(ImportInfo(raw=path, module=path, symbols=[alias] if alias else []))

    for node, _ in captures:
        key = (node.start_byte, node.end_byte)
        if key in seen:
            continue
        seen.add(key)
        for child in node.named_children:
            if child.type == "import_spec":
                _add_spec(child)
            elif child.type == "import_spec_list":
                for spec in child.named_children:
                    if spec.type == "import_spec":
                        _add_spec(spec)

    return results

def _extract_python_classes(source_bytes: bytes, root_node) -> List[str]:
    language = get_language("python")
    query = language.query("(class_definition name: (identifier) @class_name)")
    return list(dict.fromkeys(_text(n, source_bytes) for n, _ in query.captures(root_node)))


def _extract_js_ts_classes(source_bytes: bytes, root_node, lang: str) -> List[str]:
    language = get_language(lang)
    names: List[str] = []
    for name_type in ("type_identifier", "identifier"):
        try:
            query = language.query(f"(class_declaration name: ({name_type}) @class_name)")
            names.extend(_text(n, source_bytes) for n, _ in query.captures(root_node))
        except Exception:
            continue
    return list(dict.fromkeys(names))
def _extract_rust_classes(source_bytes: bytes, root_node) -> List[str]:
    language = get_language("rust")
    query = language.query("""
        (struct_item name: (type_identifier) @name)
        (enum_item name: (type_identifier) @name)
        (trait_item name: (type_identifier) @name)
    """)
    return list(dict.fromkeys(_text(n, source_bytes) for n, _ in query.captures(root_node)))


def _extract_c_cpp_classes(source_bytes: bytes, root_node, lang: str) -> List[str]:
    language = get_language(lang)
    names: List[str] = []
    try:
        query = language.query("""
            (struct_specifier name: (type_identifier) @name)
        """)
        names.extend(_text(n, source_bytes) for n, _ in query.captures(root_node))
    except Exception:
        pass
    if lang == "cpp":
        try:
            query = language.query("(class_specifier name: (type_identifier) @name)")
            names.extend(_text(n, source_bytes) for n, _ in query.captures(root_node))
        except Exception:
            pass
    return list(dict.fromkeys(names))


def _extract_go_classes(source_bytes: bytes, root_node) -> List[str]:
    """Go doesn't have classes, but extract named struct types from type declarations."""
    language = get_language("go")
    try:
        query = language.query("""
            (type_declaration (type_spec name: (type_identifier) @name))
        """)
        return list(dict.fromkeys(_text(n, source_bytes) for n, _ in query.captures(root_node)))
    except Exception:
        return []
def _extract_python_functions(source_bytes: bytes, root_node) -> List[str]:
    """Extract top-level function definitions (not methods inside classes)."""
    language = get_language("python")
    # Only match function_definition that is a direct child of module
    query = language.query("""
        (module (function_definition name: (identifier) @fn_name))
    """)
    return list(dict.fromkeys(_text(n, source_bytes) for n, _ in query.captures(root_node)))
def _extract_js_ts_functions(source_bytes: bytes, root_node, lang: str) -> List[str]:
    language = get_language(lang)
    names: List[str] = []
    try:
        query = language.query("(function_declaration name: (identifier) @fn_name)")
        names.extend(_text(n, source_bytes) for n, _ in query.captures(root_node))
    except Exception:
        pass
    try:
        query = language.query("""
            (export_statement
              declaration: (function_declaration name: (identifier) @fn_name))
        """)
        names.extend(_text(n, source_bytes) for n, _ in query.captures(root_node))
    except Exception:
        pass
    return list(dict.fromkeys(names))


def _extract_rust_functions(source_bytes: bytes, root_node) -> List[str]:
    language = get_language("rust")
    query = language.query("(function_item name: (identifier) @fn_name)")
    return list(dict.fromkeys(_text(n, source_bytes) for n, _ in query.captures(root_node)))


def _extract_c_cpp_functions(source_bytes: bytes, root_node, lang: str) -> List[str]:
    language = get_language(lang)
    try:
        query = language.query("""
            (function_definition
              declarator: (function_declarator
                declarator: (identifier) @fn_name))
        """)
        return list(dict.fromkeys(_text(n, source_bytes) for n, _ in query.captures(root_node)))
    except Exception:
        return []


def _extract_go_functions(source_bytes: bytes, root_node) -> List[str]:
    language = get_language("go")
    query = language.query("(function_declaration name: (identifier) @fn_name)")
    return list(dict.fromkeys(_text(n, source_bytes) for n, _ in query.captures(root_node)))


def parse_file(file_path: str, lang: Optional[str] = None) -> ParseResult:
    if not TREE_SITTER_AVAILABLE:
        return ParseResult(has_error=True)

    if lang is None:
        lang = get_language_for_file(file_path)
    if lang is None:
        return ParseResult()

    try:
        path = Path(file_path)
        source_text = path.read_text(encoding="utf-8", errors="replace")
        source_bytes = source_text.encode("utf-8", errors="replace")
    except Exception:
        return ParseResult(has_error=True)

    try:
        parser = get_parser(lang)
        tree = parser.parse(source_bytes)
        root = tree.root_node
    except Exception:
        return ParseResult(has_error=True)

    has_error = getattr(root, "has_error", False)
    imports: List[ImportInfo] = []
    if lang == "python":
        imports = _extract_python_imports(source_bytes, root)
    elif lang in ("javascript", "typescript"):
        imports = _extract_js_family_imports(source_bytes, root, lang)
    elif lang == "rust":
        imports = _extract_rust_imports(source_bytes, root)
    elif lang in ("c", "cpp"):
        imports = _extract_c_cpp_imports(source_bytes, root, lang)
    elif lang == "go":
        imports = _extract_go_imports(source_bytes, root)
    classes: List[str] = []
    if lang == "python":
        classes = _extract_python_classes(source_bytes, root)
    elif lang in ("javascript", "typescript"):
        classes = _extract_js_ts_classes(source_bytes, root, lang)
    elif lang == "rust":
        classes = _extract_rust_classes(source_bytes, root)
    elif lang in ("c", "cpp"):
        classes = _extract_c_cpp_classes(source_bytes, root, lang)
    elif lang == "go":
        classes = _extract_go_classes(source_bytes, root)
    functions: List[str] = []
    if lang == "python":
        functions = _extract_python_functions(source_bytes, root)
    elif lang in ("javascript", "typescript"):
        functions = _extract_js_ts_functions(source_bytes, root, lang)
    elif lang == "rust":
        functions = _extract_rust_functions(source_bytes, root)
    elif lang in ("c", "cpp"):
        functions = _extract_c_cpp_functions(source_bytes, root, lang)
    elif lang == "go":
        functions = _extract_go_functions(source_bytes, root)

    return ParseResult(
        imports=imports,
        classes=classes,
        functions=functions,
        has_error=has_error,
    )
def parse_file_from_content(content: str, lang: str) -> ParseResult:
    if not TREE_SITTER_AVAILABLE:
        return ParseResult(has_error=True)

    if lang not in set(SUPPORTED_LANGUAGES.values()):
        return ParseResult()

    source_bytes = content.encode("utf-8", errors="replace")

    try:
        parser = get_parser(lang)
        tree = parser.parse(source_bytes)
        root = tree.root_node
    except Exception:
        return ParseResult(has_error=True)

    has_error = getattr(root, "has_error", False)

    imports: List[ImportInfo] = []
    classes: List[str] = []
    functions: List[str] = []

    if lang == "python":
        imports = _extract_python_imports(source_bytes, root)
        classes = _extract_python_classes(source_bytes, root)
        functions = _extract_python_functions(source_bytes, root)
    elif lang in ("javascript", "typescript"):
        imports = _extract_js_family_imports(source_bytes, root, lang)
        classes = _extract_js_ts_classes(source_bytes, root, lang)
        functions = _extract_js_ts_functions(source_bytes, root, lang)
    elif lang == "rust":
        imports = _extract_rust_imports(source_bytes, root)
        classes = _extract_rust_classes(source_bytes, root)
        functions = _extract_rust_functions(source_bytes, root)
    elif lang in ("c", "cpp"):
        imports = _extract_c_cpp_imports(source_bytes, root, lang)
        classes = _extract_c_cpp_classes(source_bytes, root, lang)
        functions = _extract_c_cpp_functions(source_bytes, root, lang)
    elif lang == "go":
        imports = _extract_go_imports(source_bytes, root)
        classes = _extract_go_classes(source_bytes, root)
        functions = _extract_go_functions(source_bytes, root)

    return ParseResult(imports=imports, classes=classes, functions=functions, has_error=has_error)
def verify_symbols(
    imported_symbols: List[str],
    target_classes: List[str],
    target_functions: List[str],
) -> List[str]:
    if not imported_symbols:
        return []

    available = set(target_classes) | set(target_functions)
    
    if "*" in imported_symbols:
        return []

    missing = [sym for sym in imported_symbols if sym not in available]
    return missing
