"""Normalize error text into a stable signature (class + hash)."""

from __future__ import annotations

import hashlib
import re
from typing import Tuple


_NUM_RE = re.compile(r"\d+")
_HEX_RE = re.compile(r"0x[0-9a-fA-F]+")
_PATH_RE = re.compile(r"(/[^\s:'\"]+)")
_QUOTE_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_LINENO_RE = re.compile(r"line\s+\d+", re.IGNORECASE)


_ERROR_CLASSES = [
    # (regex, label)
    (re.compile(r"ModuleNotFoundError|ImportError|unresolved import|cannot find module|Module .+ not found", re.I), "missing_module"),
    (re.compile(r"SyntaxError|parse error|unexpected token|unexpected EOF", re.I), "syntax_error"),
    (re.compile(r"TypeError|is not a function|not callable", re.I), "type_error"),
    (re.compile(r"AttributeError|has no attribute|undefined method", re.I), "attribute_error"),
    (re.compile(r"NameError|not defined|cannot find value|cannot find symbol", re.I), "name_error"),
    (re.compile(r"AssertionError|assert\s+", re.I), "assertion_error"),
    (re.compile(r"PermissionError|permission denied|EACCES", re.I), "permission_error"),
    (re.compile(r"FileNotFoundError|no such file|ENOENT", re.I), "file_not_found"),
    (re.compile(r"ConnectionError|connection refused|ECONNREFUSED|timed? ?out", re.I), "connection_error"),
    (re.compile(r"compilation error|failed to compile|error\[E\d+\]|cargo build", re.I), "compile_error"),
    (re.compile(r"test failed|FAIL(ED)?|\d+ failed", re.I), "test_failure"),
]


def normalize_error(text: str) -> str:
    """Collapse dynamic bits (numbers, paths, quoted strings) so similar errors
    hash to the same signature."""
    if not text:
        return ""
    s = text.strip()
    # Keep only the last ~1000 chars — error tails are the informative part.
    s = s[-1000:]
    s = _HEX_RE.sub("<HEX>", s)
    s = _PATH_RE.sub("<PATH>", s)
    s = _QUOTE_RE.sub("<STR>", s)
    s = _LINENO_RE.sub("line <N>", s)
    s = _NUM_RE.sub("<N>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def error_signature(text: str) -> Tuple[str, str]:
    """Return (error_class, stable_hash). Both are empty if text is blank."""
    if not text or not text.strip():
        return "", ""
    klass = ""
    for pat, label in _ERROR_CLASSES:
        if pat.search(text):
            klass = label
            break
    norm = normalize_error(text)
    h = hashlib.sha1(norm.encode("utf-8", errors="replace")).hexdigest()[:12]
    return klass, h
