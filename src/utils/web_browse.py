"""Fetch a web page's readable text.

Prefers browser-harness (real Chrome over CDP via a Unix-socket daemon) for
JS-rendered pages; falls back to plain HTTP via urllib when the daemon
isn't available or the helpers can't be imported.

Small monkeypatch seams (`_load_bh_helpers`, `_daemon_socket_present`,
`_http_open`) exist so tests can exercise the HTTP fallback path without
network or daemon access.
"""

import importlib
import os
import re
import urllib.request
from typing import Any, Dict, Optional


def _load_bh_helpers():
    """Lazy import of browser-harness helpers. Returns the module or None."""
    for name in ("browser_harness.helpers", "browser_use.harness.helpers"):
        try:
            return importlib.import_module(name)
        except Exception:
            continue
    return None


def _daemon_socket_present() -> bool:
    name = os.environ.get("BROWSER_HARNESS_NAME", "default")
    return os.path.exists(f"/tmp/bu-{name}.sock")


def _http_open(url: str, timeout: float):
    """Seam for tests — opens a plain HTTP(S) connection via urllib."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (alphastack browse_url)"},
    )
    return urllib.request.urlopen(req, timeout=timeout)


_TAG_STRIP_RE = re.compile(r"(?s)<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style).*?</\1>")
_WHITESPACE_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")


def _extract_text(html: str, max_chars: int = 8000) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_STRIP_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text[:max_chars]


def _extract_title(html: str) -> str:
    m = _TITLE_RE.search(html)
    if not m:
        return ""
    return _WHITESPACE_RE.sub(" ", m.group(1)).strip()


def _fetch_http(url: str, extract: str, timeout: float, max_chars: int) -> Dict[str, Any]:
    try:
        with _http_open(url, timeout=timeout) as resp:
            raw = resp.read()
    except Exception as e:
        return {"success": False, "mode": "http", "url": url, "error": f"http fetch failed: {e}"}

    try:
        html = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    except Exception:
        html = str(raw)

    title = _extract_title(html)
    content = html[:max_chars] if extract == "html" else _extract_text(html, max_chars=max_chars)
    return {
        "success": True,
        "mode": "http",
        "url": url,
        "title": title,
        "content": content,
    }


def _fetch_browser(
    helpers, url: str, extract: str, timeout: float, max_chars: int
) -> Dict[str, Any]:
    try:
        helpers.goto(url)
        if hasattr(helpers, "wait_for_load"):
            try:
                helpers.wait_for_load(timeout=timeout)
            except TypeError:
                helpers.wait_for_load()
        title = ""
        try:
            title = helpers.js("document.title") or ""
        except Exception:
            title = ""
        if extract == "html":
            content = helpers.js("document.documentElement.outerHTML") or ""
        else:
            content = helpers.js("document.body ? document.body.innerText : ''") or ""
    except Exception as e:
        return {"success": False, "mode": "browser", "url": url, "error": f"browser fetch failed: {e}"}

    if not isinstance(content, str):
        content = str(content)

    return {
        "success": True,
        "mode": "browser",
        "url": url,
        "title": str(title or ""),
        "content": content[:max_chars],
    }


def fetch_url(
    url: str,
    extract: str = "text",
    timeout: float = 20.0,
    max_chars: int = 8000,
    use_browser: Optional[bool] = None,
) -> Dict[str, Any]:
    """Fetch `url` and return readable content.

    Strategy:
      1. Use browser-harness when available (daemon socket present or caller
         forces use_browser=True).
      2. Otherwise fall back to plain HTTP via urllib.

    Returns a dict with keys: success, mode ("browser"|"http"), url, title,
    content, error (optional).
    """
    if not url:
        return {"success": False, "error": "url is required"}

    want_browser = use_browser if use_browser is not None else _daemon_socket_present()

    if want_browser:
        helpers = _load_bh_helpers()
        if helpers is not None:
            result = _fetch_browser(helpers, url, extract, timeout, max_chars)
            if result.get("success"):
                return result
            # Fall through to HTTP on browser failure
            http_result = _fetch_http(url, extract, timeout, max_chars)
            if http_result.get("success"):
                http_result["browser_fallback_reason"] = result.get("error", "")
            return http_result

    return _fetch_http(url, extract, timeout, max_chars)
