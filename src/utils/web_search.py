"""DuckDuckGo web search (ddgs) wrapper with per-run LRU cache.

Exposes a `run_search` function used by ToolHandler. The ddgs import is
lazy via `_load_ddgs` so runs that never call the tool don't pay the
import cost, and tests can monkeypatch a fake.
"""

from collections import OrderedDict
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple


class WebSearchCache:
    """Small thread-safe LRU for search results."""

    def __init__(self, max_entries: int = 64):
        self._data: "OrderedDict[Tuple, List[Dict[str, str]]]" = OrderedDict()
        self._max = max_entries
        self._lock = Lock()

    def get(self, key: Tuple) -> Optional[List[Dict[str, str]]]:
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def put(self, key: Tuple, value: List[Dict[str, str]]) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)


def _load_ddgs():
    """Lazy import seam — returns the DDGS class. Tests monkeypatch this."""
    from ddgs import DDGS
    return DDGS


def run_search(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: str = "moderate",
    cache: Optional[WebSearchCache] = None,
) -> Dict[str, Any]:
    """Search the web via DuckDuckGo.

    Returns {"success": bool, "cached": bool, "results": [...], "error": str?}.
    Each result is {"title", "url", "snippet"} with snippet truncated to
    300 chars. max_results is clamped to [1, 10].
    """
    if not query:
        return {"success": False, "error": "query is required"}

    n = max(1, min(int(max_results or 5), 10))
    key = (query.strip().lower(), n, region, safesearch)

    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return {"success": True, "cached": True, "results": hit}

    try:
        DDGS = _load_ddgs()
    except ImportError:
        return {
            "success": False,
            "error": "ddgs not installed — add 'ddgs' to dependencies",
        }

    try:
        with DDGS() as d:
            raw = list(d.text(query, region=region, safesearch=safesearch, max_results=n))
    except Exception as e:
        return {"success": False, "error": f"search failed: {e}"}

    results: List[Dict[str, str]] = []
    for r in raw:
        snippet = (r.get("body") or r.get("snippet") or "") or ""
        results.append({
            "title": r.get("title") or "",
            "url": r.get("href") or r.get("url") or "",
            "snippet": snippet[:300],
        })

    if cache is not None:
        cache.put(key, results)

    return {"success": True, "cached": False, "results": results}
