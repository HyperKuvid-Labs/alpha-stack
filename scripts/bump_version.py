from __future__ import annotations

import argparse
import pathlib
import re
import sys


VERSION_LINE_RE = re.compile(r'^(\s*version\s*=\s*")(?P<version>[0-9]+\.[0-9]+\.[0-9]+)("\s*)$')


def bump(version: str, part: str) -> str:
    major, minor, patch = (int(value) for value in version.split("."))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump pyproject.toml version")
    parser.add_argument(
        "--part",
        choices=["major", "minor", "patch"],
        default="patch",
        help="Version part to bump (default: patch)",
    )
    parser.add_argument(
        "--file",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml)",
    )
    args = parser.parse_args()

    file_path = pathlib.Path(args.file)
    if not file_path.exists():
        print(f"Error: {file_path} not found", file=sys.stderr)
        return 1

    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)

    in_project_section = False
    found_version = False
    old_version = None

    for index, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            in_project_section = stripped == "[project]"
            continue

        if in_project_section:
            match = VERSION_LINE_RE.match(line.rstrip("\n"))
            if match:
                old_version = match.group("version")
                new_version = bump(old_version, args.part)
                lines[index] = f'{match.group(1)}{new_version}{match.group(3)}\n'
                found_version = True
                break

    if not found_version or old_version is None:
        print("Error: Could not find [project].version in pyproject.toml", file=sys.stderr)
        return 1

    file_path.write_text("".join(lines), encoding="utf-8")
    print(f"Version bumped: {old_version} -> {new_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
