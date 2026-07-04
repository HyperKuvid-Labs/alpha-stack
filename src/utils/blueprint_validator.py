"""Deterministic structural validation for Phase 1 blueprints.

The blueprint prompt states rules the model must follow (unit tests per module,
every module wired in, entry point present, valid dependency paths). Weak
models drop these under long structured output, and same-model critics miss
what the generator missed. These checks are mechanical, so they are enforced
in code: each returned string is a concrete issue fed back through the
blueprint refinement path.
"""

import json
import os
from typing import Any, Dict, List

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".c", ".cc", ".cpp",
    ".cu", ".cuh", ".h", ".hpp", ".java", ".rb", ".php", ".swift", ".kt",
}

ENTRY_STEMS = {"main", "app", "index", "cli", "server", "run", "__main__"}

REQUIRED_CONTRACT_FIELDS = ("purpose", "behaviors", "interfaces", "dependencies", "external_packages")


def _norm(path: str) -> str:
    return os.path.normpath(str(path).strip())


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _is_test_file(path: str) -> bool:
    parts = [p.lower() for p in _norm(path).split(os.sep)]
    if any(p in ("tests", "test", "__tests__", "spec") for p in parts[:-1]):
        return True
    base = parts[-1]
    stem = os.path.splitext(base)[0]
    return (
        stem.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith(".test")
        or stem.endswith(".spec")
    )


def _is_code_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in CODE_EXTENSIONS


def _is_module(path: str) -> bool:
    """A source module: code, not a test, not an __init__, not an entry point."""
    if not _is_code_file(path) or _is_test_file(path):
        return False
    stem = _stem(path).lower()
    return stem not in ENTRY_STEMS and stem != "__init__"


def _contract_dependencies(contract: Any) -> List[str]:
    if isinstance(contract, dict):
        deps = contract.get("dependencies")
        if isinstance(deps, list):
            return [_norm(d) for d in deps if isinstance(d, str) and d.strip()]
    return []


def validate_blueprint(file_formats: Dict[str, Any], folder_structure: str = "") -> List[str]:
    """Run all structural checks. Returns concrete issues (empty when clean)."""
    issues: List[str] = []
    paths = {_norm(p): contract for p, contract in file_formats.items()}
    code_files = [p for p in paths if _is_code_file(p)]
    test_files = [p for p in paths if _is_test_file(p)]
    modules = [p for p in paths if _is_module(p)]

    # 0. Every contracted file must appear in the folder structure tree.
    if folder_structure.strip():
        for path in paths:
            if os.path.basename(path) not in folder_structure:
                issues.append(
                    f"'{path}' has a contract but does not appear in folder_structure — "
                    f"the tree and the contracts must list exactly the same files."
                )

    # 1. Contracts must be dicts with the required fields.
    for path, contract in paths.items():
        if not isinstance(contract, dict):
            issues.append(
                f"Contract for '{path}' is not a JSON object — every file needs a full contract."
            )
            continue
        if _is_code_file(path):
            missing = [f for f in REQUIRED_CONTRACT_FIELDS if f not in contract]
            if missing:
                issues.append(
                    f"Contract for '{path}' is missing required field(s): {', '.join(missing)}."
                )

    # 2. An entry point must exist.
    has_entry = any(
        _stem(p).lower() in ENTRY_STEMS and _is_code_file(p) and not _is_test_file(p)
        for p in paths
    ) or any(os.path.basename(p).lower() == "index.html" for p in paths)
    if not has_entry:
        issues.append(
            "No entry point file found (main.py, app.py, main.go, index.ts, index.html, ...). "
            "Add the entry point with a contract describing the exact startup sequence."
        )

    # 3. Every source module needs a unit-test file that targets it.
    for module in modules:
        stem = _stem(module).lower()
        covered = False
        for test in test_files:
            if stem and stem in _stem(test).lower():
                covered = True
                break
            contract_text = json.dumps(paths[test]) if isinstance(paths[test], dict) else str(paths[test])
            if module in contract_text or (len(stem) >= 3 and stem in contract_text.lower()):
                covered = True
                break
        if not covered:
            issues.append(
                f"No unit-test file covers '{module}'. Add a test file (e.g. "
                f"tests/test_{_stem(module)}{os.path.splitext(module)[1]}) whose contract "
                f"names it as module_under_test."
            )

    # 4. Wiring: every module must appear in some non-test contract's
    # dependencies — a module imported only by its tests is dead code in the app.
    all_deps: Dict[str, List[str]] = {p: _contract_dependencies(c) for p, c in paths.items()}
    for module in modules:
        wired = any(
            module in deps
            for p, deps in all_deps.items()
            if p != module and not _is_test_file(p)
        )
        if not wired:
            issues.append(
                f"Module '{module}' is not listed in any other file's `dependencies` — "
                f"it will be generated but never imported (dead code). Wire it into the "
                f"entry point or the module that should use it."
            )

    # 5. Dependency paths must reference files that exist in the blueprint.
    for path, deps in all_deps.items():
        for dep in deps:
            if dep not in paths:
                issues.append(
                    f"Contract for '{path}' lists dependency '{dep}', which is not a file "
                    f"in the blueprint. Fix the path or add the missing file."
                )

    # 6. The project needs at least one test file, and one integration test.
    if code_files and not test_files:
        issues.append(
            "The blueprint contains no test files at all. Add unit tests per module "
            "plus at least one integration test."
        )
    elif test_files:
        has_integration = any(
            "integration" in p.lower()
            or "integration" in (json.dumps(paths[p]).lower() if isinstance(paths[p], dict) else "")
            for p in test_files
        )
        if not has_integration:
            issues.append(
                "No integration test found. Add at least one test file that exercises "
                "the full application end to end (e.g. tests/test_integration.py)."
            )

    return issues[:10]
