"""Embedder with graceful fallback.

Primary backend: sentence-transformers MiniLM (384-dim) + faiss IndexFlatIP.
Fallback backend: hashed term-vector (384-dim, L2-normalized) + numpy cosine.

The Embedder class exposes three operations:
  - embed(text) -> np.ndarray              (single)
  - embed_batch(texts) -> np.ndarray        (N x D)
  - topk(query_emb, ids, embs, k) -> list[(id, score)]

Loading is lazy: the heavy models aren't imported until the first embed call.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
from typing import List, Sequence, Tuple

import numpy as np


EMBED_DIM = 384
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder:
    """Lazy-initialized embedder with sentence-transformers preferred, hashed fallback."""

    _lock = threading.Lock()
    _instance: "Embedder | None" = None

    def __init__(self):
        self._model = None
        self._backend: str | None = None  # "st" or "hash"
        self._ready = False

    @classmethod
    def get(cls) -> "Embedder":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            if os.environ.get("ALPHASTACK_EMBED_BACKEND", "").lower() == "hash":
                self._backend = "hash"
                self._ready = True
                return
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                cache_dir = os.path.expanduser("~/.cache/alphastack/models")
                os.makedirs(cache_dir, exist_ok=True)
                self._model = SentenceTransformer(_MODEL_NAME, cache_folder=cache_dir)
                self._backend = "st"
            except Exception:
                self._model = None
                self._backend = "hash"
            self._ready = True

    @property
    def backend(self) -> str:
        self._ensure_ready()
        return self._backend or "hash"

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def embed(self, text: str) -> np.ndarray:
        return self.embed_batch([text or ""])[0]

    def embed_batch(self, texts: Sequence[str]) -> np.ndarray:
        self._ensure_ready()
        if not texts:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        clean = [(t or "")[:2000] for t in texts]
        if self._backend == "st" and self._model is not None:
            try:
                vecs = self._model.encode(
                    clean,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                return vecs.astype(np.float32)
            except Exception:
                # Fall through to hashed backend on runtime failure.
                pass
        return np.stack([_hashed_embed(t) for t in clean]).astype(np.float32)

    # ------------------------------------------------------------------
    # Top-k search over a pre-computed matrix
    # ------------------------------------------------------------------

    def topk(
        self,
        query_emb: np.ndarray,
        ids: Sequence[int],
        embs: np.ndarray,
        k: int,
    ) -> List[Tuple[int, float]]:
        """Cosine similarity top-k. Returns [(id, score)] sorted descending."""
        if len(ids) == 0 or embs.size == 0:
            return []
        q = query_emb.reshape(-1)
        q_norm = np.linalg.norm(q)
        if q_norm < 1e-9:
            return []
        qn = q / q_norm
        # Assume embs are already normalized (our embedders return normalized).
        scores = embs @ qn
        k = min(k, len(ids))
        if k <= 0:
            return []
        # argpartition for speed then sort
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
        return [(int(ids[i]), float(scores[i])) for i in idx]


# ----------------------------------------------------------------------
# Hashed fallback embedder — deterministic, small, no downloads.
# ----------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}|\d{2,}")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _hashed_embed(text: str) -> np.ndarray:
    """Hashed term-vector with 1- and 2-grams, L2-normalized."""
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
        vec[h % EMBED_DIM] += 1.0
    for a, b in zip(tokens, tokens[1:]):
        bg = a + " " + b
        h = int.from_bytes(hashlib.md5(bg.encode()).digest()[:4], "little")
        vec[h % EMBED_DIM] += 0.5
    # L2 normalize
    norm = math.sqrt(float(np.dot(vec, vec)))
    if norm > 1e-9:
        vec /= norm
    return vec


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity; assumes 1-D arrays, handles zero vectors safely."""
    an = np.linalg.norm(a)
    bn = np.linalg.norm(b)
    if an < 1e-9 or bn < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (an * bn))
