"""CubeSession: project-tree mirroring + lifecycle.

We don't talk to a real CubeSandbox — instead we build a session via
``CubeSession.__new__`` and hand it a MagicMock ``sandbox`` so we can
verify which paths get uploaded and which junk dirs get skipped.
"""

from __future__ import annotations

import os
import threading
from unittest.mock import MagicMock

import pytest

from src.sandbox.cube import CubeSession, SandboxStartupError


def _seed_project(tmp_path):
    """Layout a tiny project tree with junk dirs we expect to be skipped."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("// junk\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.pyc").write_text("garbage")
    return tmp_path


def _new_session(project_root, sandbox):
    s = CubeSession.__new__(CubeSession)
    s.project_root = os.path.abspath(project_root)
    s.template_id = "tpl_fake"
    s.workdir = "/workspace"
    s.api_url = None
    s.api_key = None
    s._closed = False
    s._lock = threading.Lock()
    s.sandbox = sandbox
    return s


def test_iter_project_files_skips_junk(tmp_path):
    _seed_project(tmp_path)
    session = _new_session(tmp_path, sandbox=MagicMock())

    files = sorted(rel for rel, _ in session._iter_project_files())
    assert files == ["src/main.py"]


def test_push_file_writes_to_workspace(tmp_path):
    _seed_project(tmp_path)
    sb = MagicMock()
    session = _new_session(tmp_path, sandbox=sb)

    session.push_file("src/main.py")

    sb.files.write.assert_called_once()
    args = sb.files.write.call_args[0]
    assert args[0] == "/workspace/src/main.py"
    assert args[1] == b"print('hi')\n"


def test_upload_project_uploads_only_non_junk(tmp_path):
    _seed_project(tmp_path)
    sb = MagicMock()
    session = _new_session(tmp_path, sandbox=sb)

    session._upload_project()

    written = [call.args[0] for call in sb.files.write.call_args_list]
    assert written == ["/workspace/src/main.py"]


def test_close_is_idempotent(tmp_path):
    _seed_project(tmp_path)
    sb = MagicMock()
    session = _new_session(tmp_path, sandbox=sb)

    session.close()
    session.close()  # Second call must not raise or kill twice.

    assert sb.kill.call_count == 1


def test_missing_template_id_raises():
    with pytest.raises(SandboxStartupError):
        CubeSession(project_root="/tmp/anywhere", template_id="")


def test_delete_file_uses_rm(tmp_path):
    _seed_project(tmp_path)
    sb = MagicMock()
    session = _new_session(tmp_path, sandbox=sb)

    session.delete_file("src/main.py")
    sb.commands.run.assert_called_once_with("rm -f '/workspace/src/main.py'")


def test_mkdir_uses_mkdir_p(tmp_path):
    sb = MagicMock()
    session = _new_session(tmp_path, sandbox=sb)

    session.mkdir("src/new_dir")
    sb.commands.run.assert_called_once_with("mkdir -p '/workspace/src/new_dir'")
