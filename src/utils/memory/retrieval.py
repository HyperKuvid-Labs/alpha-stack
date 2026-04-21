"""Relevance-heavy scoring over episodes + insights."""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .embed import Embedder


# Weights from Park et al. (Generative Agents). Relevance heavy, recency as
# tie-breaker. Tuned empirically for code-fix episodes.
W_RELEVANCE = 0.5
W_IMPORTANCE = 0.3
W_RECENCY = 0.2

# Recency half-life in seconds (6 hours). Newer episodes get a larger bonus.
RECENCY_TAU = 6 * 3600.0


def _recency(row_ts: float, now: float) -> float:
    dt = max(0.0, now - row_ts)
    return math.exp(-dt / RECENCY_TAU)


def score_and_topk(
    query_emb: np.ndarray,
    rows: Sequence[Dict],
    now: float,
    k: int,
    *,
    min_score: float = 0.0,
) -> List[Tuple[Dict, float]]:
    """Return top-k rows by combined score. Each row must carry an 'embedding'
    numpy vector, 'importance' float, and 'ts' float."""
    if not rows:
        return []
    q = query_emb.reshape(-1)
    qn = np.linalg.norm(q)
    if qn < 1e-9:
        # No query signal: fall back to importance + recency
        scored = [
            (r, W_IMPORTANCE * float(r.get("importance", 0.0))
             + W_RECENCY * _recency(float(r.get("ts", 0.0)), now))
            for r in rows
        ]
    else:
        qhat = q / qn
        scored = []
        for r in rows:
            emb = r.get("embedding")
            if emb is None:
                rel = 0.0
            else:
                emb_vec = np.asarray(emb, dtype=np.float32).reshape(-1)
                en = np.linalg.norm(emb_vec)
                rel = float(np.dot(qhat, emb_vec) / en) if en > 1e-9 else 0.0
            importance = float(r.get("importance", 0.0))
            rec = _recency(float(r.get("ts", 0.0)), now)
            s = W_RELEVANCE * rel + W_IMPORTANCE * importance + W_RECENCY * rec
            scored.append((r, s))
    scored = [s for s in scored if s[1] >= min_score]
    scored.sort(key=lambda t: -t[1])
    return scored[:k]


def tag_overlap_filter(
    rows: Sequence[Dict], context_tags: Sequence[str]
) -> List[Dict]:
    """Return rows whose tag set intersects context_tags."""
    if not context_tags:
        return list(rows)
    ctx = {t for t in context_tags if t}
    return [r for r in rows if ctx & set(r.get("tags", []) or [])]


def embed_query(text: str) -> np.ndarray:
    """Convenience: embed a single query string."""
    return Embedder.get().embed(text or "")
