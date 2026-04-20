"""`generate_tree` parses the ASCII folder_structure the model emits."""

from src.generator import generate_tree


def test_simple_tree():
    structure = """
my_project/
├── src/
│   └── main.py
└── requirements.txt
""".strip()
    root = generate_tree(structure, project_name="")
    assert root is not None
    assert root.value == "my_project"
    names = [c.value for c in root.children]
    assert "src" in names
    assert "requirements.txt" in names


def test_nested_tree():
    structure = """
app/
├── app/
│   ├── __init__.py
│   └── main.py
└── pyproject.toml
""".strip()
    root = generate_tree(structure, project_name="")
    assert root.value == "app"
    inner = next((c for c in root.children if c.value == "app"), None)
    assert inner is not None
    inner_names = [c.value for c in inner.children]
    assert "__init__.py" in inner_names
    assert "main.py" in inner_names


def test_tree_with_comments():
    structure = """
foo/
├── src/  # source code
│   └── main.rs  # entry point
└── Cargo.toml
""".strip()
    root = generate_tree(structure, project_name="")
    assert root.value == "foo"
    src = next((c for c in root.children if c.value == "src"), None)
    assert src is not None
    # Comments should be stripped from names
    main_rs = next((c for c in src.children if "main" in c.value), None)
    assert main_rs is not None
    assert "#" not in main_rs.value


def test_tree_wrapped_in_code_fences():
    """Models often wrap in ```."""
    structure = """```
root/
└── main.py
```"""
    root = generate_tree(structure, project_name="")
    assert root is not None
    assert root.value == "root"
