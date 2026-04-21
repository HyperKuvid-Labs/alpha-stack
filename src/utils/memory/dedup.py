"""Loop / duplicate-action detector.

Maintains a sliding deque of the last N action signatures. When the same
signature fires ≥ threshold times, the caller emits a LoopWarn so the agent
sees its repeated failures in-context on the next round.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, deque
from typing import Deque, Dict, Optional


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_detail(detail: str) -> str:
    if not detail:
        return ""
    s = detail.strip().lower()
    s = _WHITESPACE_RE.sub(" ", s)
    # Collapse numbers so "retry 3" and "retry 4" hash the same.
    s = re.sub(r"\d+", "<N>", s)
    return s[:200]


def _sig(action: str, file: str, detail: str) -> str:
    norm = f"{action}|{file}|{_normalize_detail(detail)}"
    return hashlib.md5(norm.encode("utf-8", errors="replace")).hexdigest()[:10]


class LoopDetector:
    """Tracks recent action signatures and flags repeats."""

    def __init__(self, window: int = 50, threshold: int = 3):
        self.window = window
        self.threshold = threshold
        self._hashes: Deque[str] = deque(maxlen=window)
        self._last_outcome: Dict[str, str] = {}
        self._last_payload: Dict[str, Dict[str, str]] = {}

    def observe(
        self,
        action: str,
        file: str,
        detail: str,
        outcome: str = "",
    ) -> Optional[str]:
        """Record one action. Returns a warning string if this action has now
        been seen ≥ threshold times in the window, else None."""
        sig = _sig(action, file, detail)
        self._hashes.append(sig)
        if outcome:
            self._last_outcome[sig] = outcome
        self._last_payload[sig] = {"action": action, "file": file, "detail": detail}
        count = sum(1 for h in self._hashes if h == sig)
        if count >= self.threshold:
            payload = self._last_payload.get(sig, {})
            outcome_tag = self._last_outcome.get(sig, "unknown")
            return (
                f"⚠ tried {payload.get('action','?')} "
                f"{payload.get('file','')} {count}× already — last outcome: {outcome_tag}"
            )
        return None

    def snapshot_warnings(self, max_items: int = 5) -> list[str]:
        """Return warning strings for every signature currently ≥ threshold."""
        if not self._hashes:
            return []
        counts = Counter(self._hashes)
        warns = []
        for sig, n in counts.most_common():
            if n < self.threshold:
                break
            payload = self._last_payload.get(sig, {})
            outcome_tag = self._last_outcome.get(sig, "unknown")
            warns.append(
                f"⚠ tried {payload.get('action','?')} "
                f"{payload.get('file','')} {n}× already — last outcome: {outcome_tag}"
            )
            if len(warns) >= max_items:
                break
        return warns
