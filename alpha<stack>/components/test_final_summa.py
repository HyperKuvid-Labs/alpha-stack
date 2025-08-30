import os
import pathlib
import pytest
import shutil
import tempfile
from unittest import mock

# Modules under test
from determine_tech_stack import gen_and_store_ts
from rgen_fs import generate_structure
from tree_thing import generate_fs
from generatable_files import get_generatable_files
from dfs_tree_and_gen import dfs_tree_and_gen
from dependency_analyzer import DependencyAnalyzer


###############################################################################
# FIXTURES
###############################################################################
@pytest.fixture(scope="session")
def temp_workspace():
    """Create a temporary workspace directory for tests."""
    tmpdir = tempfile.mkdtemp(prefix="projtest_")
    cwd = os.getcwd()
    os.chdir(tmpdir)
    yield pathlib.Path(tmpdir)
    os.chdir(cwd)
    shutil.rmtree(tmpdir)


@pytest.fixture
def clean_docs(temp_workspace):
    """Ensure docs/ folder exists fresh."""
    docs = temp_workspace / "docs"
    docs.mkdir(exist_ok=True)
    return docs


###############################################################################
# UNIT TESTS
###############################################################################

class TestGenAndStoreTS:
    def test_generates_name_and_stores_file(self, clean_docs):
        prompt = "Build an AI tool with ML and Python"
        project_name = gen_and_store_ts(prompt)
        assert isinstance(project_name, str)
        assert len(project_name) > 0

        ts_path = clean_docs / "tech_stack_reqs.md"
        assert ts_path.exists()
        content = ts_path.read_text()
        assert "Python" in content or "AI" in content

    def test_empty_prompt(self, clean_docs):
        project_name = gen_and_store_ts("")
        assert isinstance(project_name, str)
        assert len(project_name) > 0


class TestGenerateStructure:
    def test_creates_base_structure(self, temp_workspace):
        generate_structure()
        assert (temp_workspace / "src").exists()
        assert (temp_workspace / "docs").exists()


class TestGenerateFS:
    def test_returns_tree_object(self, temp_workspace):
        generate_structure()
        tree = generate_fs(project_name="TestProj")
        assert hasattr(tree, "dfs_traverse_debug")
        assert callable(tree.dfs_traverse_debug)

    def test_count_files(self, temp_workspace):
        generate_structure()
        tree = generate_fs(project_name="TestProj")
        count = tree._count_files()
        assert isinstance(count, int)
        assert count >= 0


class TestGetGeneratableFiles:
    def test_returns_list(self, clean_docs):
        files = get_generatable_files()
        assert isinstance(files, (list, tuple))


class TestDependencyAnalyzer:
    def test_add_and_visualize(self, temp_workspace):
        da = DependencyAnalyzer()
        da.add_dependency("A", "B")
        da.add_dependency("B", "C")
        assert "A" in da.graph
        assert "B" in da.graph
        da.visualize_graph(output_file="deps.png")
        assert (temp_workspace / "deps.png").exists()


###############################################################################
# INTEGRATION TESTS
###############################################################################

class TestPipeline:
    def test_end_to_end_pipeline(self, clean_docs):
        prompt = "A scalable Python+Rust project for file handling"
        project_name = gen_and_store_ts(prompt)
        generate_structure()
        tree = generate_fs(project_name=project_name)

        # Ensure docs exist
        ts_path = clean_docs / "tech_stack_reqs.md"
        ts_content = ts_path.read_text()
        assert "Python" in ts_content or "Rust" in ts_content

        fs_path = clean_docs / "folder_structure.md"
        fs_path.write_text("Test folder structure")

        dependency_analyzer = DependencyAnalyzer()
        dfs_tree_and_gen(
            tree,
            project_desc=ts_content,
            project_name=project_name,
            parent_context="",
            current_path="",
            is_top_level=True,
            folder_structure=fs_path.read_text(),
            dependency_analyzer=dependency_analyzer,
        )
        dependency_analyzer.visualize_graph(output_file="pipeline_graph.png")
        assert (clean_docs.parent / "pipeline_graph.png").exists()

    def test_pipeline_with_missing_folder_structure(self, clean_docs):
        prompt = "Another test project"
        project_name = gen_and_store_ts(prompt)
        generate_structure()
        tree = generate_fs(project_name=project_name)

        ts_path = clean_docs / "tech_stack_reqs.md"
        ts_content = ts_path.read_text()

        dependency_analyzer = DependencyAnalyzer()
        dfs_tree_and_gen(
            tree,
            project_desc=ts_content,
            project_name=project_name,
            parent_context="",
            current_path="",
            is_top_level=True,
            folder_structure=None,
            dependency_analyzer=dependency_analyzer,
        )
        assert "graph" in dir(dependency_analyzer)


###############################################################################
# PARAMETERIZED + EDGE CASE TESTS
###############################################################################

@pytest.mark.parametrize("prompt", [
    "Small CLI project",
    "Web app with Django and React",
    "ML pipeline with PyTorch",
    "   ",  # whitespace only
])
def test_gen_and_store_various_prompts(prompt, clean_docs):
    project_name = gen_and_store_ts(prompt)
    assert isinstance(project_name, str)
    assert len(project_name.strip()) > 0


class TestRobustness:
    def test_dfs_tree_and_gen_handles_empty_desc(self, temp_workspace):
        generate_structure()
        tree = generate_fs(project_name="EdgeProj")
        dependency_analyzer = DependencyAnalyzer()

        dfs_tree_and_gen(
            tree,
            project_desc="",
            project_name="EdgeProj",
            parent_context="",
            current_path="",
            is_top_level=True,
            folder_structure="",
            dependency_analyzer=dependency_analyzer,
        )
        assert isinstance(dependency_analyzer.graph, dict)

    def test_dependency_analyzer_duplicate_edges(self):
        da = DependencyAnalyzer()
        da.add_dependency("A", "B")
        da.add_dependency("A", "B")  # duplicate
        assert "A" in da.graph
        assert len(da.graph["A"]) == 1  # should not duplicate


###############################################################################
# STRESS TESTS
###############################################################################

def test_large_prompt_pipeline(clean_docs):
    big_prompt = "Generate a huge multi-module project with AI, IoT, Blockchain, and VR/AR support. " * 20
    project_name = gen_and_store_ts(big_prompt)
    generate_structure()
    tree = generate_fs(project_name=project_name)

    ts_path = clean_docs / "tech_stack_reqs.md"
    ts_content = ts_path.read_text()

    fs_path = clean_docs / "folder_structure.md"
    fs_path.write_text("Massive folder structure")

    dependency_analyzer = DependencyAnalyzer()
    dfs_tree_and_gen(
        tree,
        project_desc=ts_content,
        project_name=project_name,
        parent_context="",
        current_path="",
        is_top_level=True,
        folder_structure=fs_path.read_text(),
        dependency_analyzer=dependency_analyzer,
    )
    assert len(dependency_analyzer.graph) >= 1
