"""Deterministic path -> import-address mapping for generated Python files.

File agents receive dependency *paths* ("loganalyze/engine.py") and were
expected to derive the import statement themselves; weak models write the
basename ("from engine import X") which Python rejects at runtime. The
mapping is mechanical, so it is computed here and injected into agent
context instead of being left to model inference.
"""

import os
from typing import Dict, Iterable


def python_import_addresses(paths: Iterable[str]) -> Dict[str, str]:
    """Map every .py path to its dotted import address.

    "loganalyze/engine.py" -> "loganalyze.engine"
    "loganalyze/__init__.py" -> "loganalyze"
    "main.py" -> "main"

    Addresses are best-effort: computed from the path even when an
    intermediate __init__.py is missing (the address is still what the
    import must be once the package is complete).
    """
    addresses: Dict[str, str] = {}
    for raw in paths:
        path = os.path.normpath(str(raw))
        if not path.endswith(".py"):
            continue
        parts = path.split(os.sep)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
            if not parts:
                continue
        else:
            parts[-1] = parts[-1][: -len(".py")]
        addresses[path] = ".".join(parts)
    return addresses


def import_guidance(filepath: str, dependencies: Iterable[str], all_paths: Iterable[str]) -> Dict:
    """Guidance block for one file's contract: its own address plus the exact
    import form for each of its Python dependencies. Empty dict when nothing
    Python is involved."""
    addresses = python_import_addresses(all_paths)
    norm = os.path.normpath(str(filepath))
    guidance: Dict = {}

    own = addresses.get(norm)
    if own:
        guidance["this_file_imports_as"] = own

    dep_imports = {}
    for dep in dependencies or []:
        dep_norm = os.path.normpath(str(dep))
        addr = addresses.get(dep_norm)
        if addr:
            dep_imports[dep_norm] = f"from {addr} import <name>"
    if dep_imports:
        guidance["import_dependencies_exactly_as"] = dep_imports
        guidance["rule"] = (
            "Use these exact absolute import forms — never bare module names "
            "(e.g. never 'from engine import X' when the module lives in a package)."
        )
    return guidance
