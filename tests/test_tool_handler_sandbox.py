"""ToolHandler must mirror successful local edits into the sandbox.

We pass a MagicMock CubeSession into ToolHandler and confirm:
  - update_file_code      → push_file(rel_path)
  - patch_file            → push_file(rel_path)
  - create_directory      → mkdir(directory_path)
  - delete_file           → delete_file(file_path)

A mirror call that raises must NOT bubble up through the tool result.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from src.utils.tools import ToolHandler


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    return tmp_path


@pytest.fixture
def session():
    sess = MagicMock()
    sess.workdir = "/workspace"
    return sess


def test_update_file_code_pushes_to_sandbox(tmp_project, session):
    handler = ToolHandler(str(tmp_project), sandbox_session=session)
    result = handler.handle_function_call(
        "update_file_code",
        {"file_path": "src/main.py", "new_content": "print('hello')\n",
         "change_description": "switch greeting"},
    )
    assert result.get("success") is True
    session.push_file.assert_called_once_with("src/main.py")


def test_create_directory_calls_mkdir(tmp_project, session):
    handler = ToolHandler(str(tmp_project), sandbox_session=session)
    result = handler.handle_function_call(
        "create_directory",
        {"directory_path": "src/new_dir"},
    )
    assert result.get("success") is True
    session.mkdir.assert_called_once_with("src/new_dir")


def test_delete_file_calls_delete(tmp_project, session):
    handler = ToolHandler(str(tmp_project), sandbox_session=session)
    result = handler.handle_function_call(
        "delete_file",
        {"file_path": "src/main.py"},
    )
    assert result.get("success") is True
    session.delete_file.assert_called_once_with("src/main.py")


def test_patch_file_pushes_to_sandbox(tmp_project, session):
    handler = ToolHandler(str(tmp_project), sandbox_session=session)
    result = handler.handle_function_call(
        "patch_file",
        {
            "file_path": "src/main.py",
            "fix_type": "full_rewrite",
            "description": "rewrite",
            "new_content": "print('rewritten')\n",
        },
    )
    assert result.get("success") is True
    session.push_file.assert_called_once_with("src/main.py")


def test_mirror_failures_do_not_break_tool_call(tmp_project):
    sess = MagicMock()
    sess.push_file.side_effect = RuntimeError("sandbox unreachable")
    handler = ToolHandler(str(tmp_project), sandbox_session=sess)

    result = handler.handle_function_call(
        "update_file_code",
        {"file_path": "src/main.py", "new_content": "x\n",
         "change_description": "test"},
    )
    # Local edit must still succeed even though the mirror raised.
    assert result.get("success") is True
    assert (tmp_project / "src" / "main.py").read_text() == "x\n"
