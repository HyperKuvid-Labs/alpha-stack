"""SQLite-backed persistence for episodes + insights.

The store owns a sqlite3.Connection (one per MemoryStore instance). All
writes are synchronous; reads happen against the same connection. Embeddings
are stored as raw float32 BLOBs.

A matching in-memory numpy matrix is rebuilt on open() and kept in sync by
append_embedding(). Retrieval operates on the in-memory matrix (FAISS is
unnecessary at these scales — a few thousand vectors cosine-scored in numpy
is sub-millisecond).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .embed import EMBED_DIM


SCHEMA_VERSION = 1


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    role TEXT NOT NULL,
    ts REAL NOT NULL,
    session INTEGER DEFAULT 0,
    action TEXT NOT NULL,
    file TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    outcome TEXT DEFAULT '',
    importance REAL DEFAULT 0.3,
    error_class TEXT DEFAULT '',
    error_hash TEXT DEFAULT '',
    embedding BLOB
);

CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(ts);
CREATE INDEX IF NOT EXISTS idx_episodes_role ON episodes(role);
CREATE INDEX IF NOT EXISTS idx_episodes_error ON episodes(error_class);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_ts REAL NOT NULL,
    last_reinforced_ts REAL NOT NULL,
    support_count INTEGER DEFAULT 1,
    tags TEXT DEFAULT '[]',
    text TEXT NOT NULL,
    embedding BLOB
);

CREATE INDEX IF NOT EXISTS idx_insights_reinforced ON insights(last_reinforced_ts);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _blob(v: Optional[np.ndarray]) -> Optional[bytes]:
    if v is None:
        return None
    return np.asarray(v, dtype=np.float32).tobytes()


def _unblob(b: Optional[bytes]) -> Optional[np.ndarray]:
    if not b:
        return None
    return np.frombuffer(b, dtype=np.float32).copy()


class MemoryDB:
    """Thin DAO over the sqlite schema above.

    Thread-safe: a single lock serializes writes; sqlite3 itself is fine for
    concurrent reads inside the process.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path  # None → in-memory
        self.run_id = uuid.uuid4().hex[:12]
        self._lock = threading.RLock()

        if db_path:
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=5.0)
        else:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)

        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            cur = self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            cur.close()
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                ("last_run_id", self.run_id),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Episodes
    # ------------------------------------------------------------------

    def insert_episode(
        self,
        *,
        role: str,
        session: int,
        action: str,
        file: str,
        detail: str,
        outcome: str,
        importance: float,
        error_class: str,
        error_hash: str,
        embedding: Optional[np.ndarray],
        ts: Optional[float] = None,
    ) -> int:
        ts = ts if ts is not None else time.time()
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO episodes
                  (run_id, role, ts, session, action, file, detail, outcome,
                   importance, error_class, error_hash, embedding)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    self.run_id, role, ts, session, action, file, detail, outcome,
                    float(importance), error_class, error_hash, _blob(embedding),
                ),
            )
            rid = int(cur.lastrowid)
            self._conn.commit()
        return rid

    def fetch_episodes(
        self,
        *,
        since_ts: Optional[float] = None,
        limit: Optional[int] = None,
        with_embeddings: bool = True,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM episodes"
        args: List[Any] = []
        if since_ts is not None:
            sql += " WHERE ts >= ?"
            args.append(since_ts)
        sql += " ORDER BY ts DESC"
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        with self._lock:
            rows = [dict(r) for r in self._conn.execute(sql, args)]
        if with_embeddings:
            for r in rows:
                r["embedding"] = _unblob(r.get("embedding"))
        else:
            for r in rows:
                r.pop("embedding", None)
        return rows

    def recent_episodes_of_run(self, run_id: str, limit: int) -> List[Dict[str, Any]]:
        with self._lock:
            rows = [
                dict(r)
                for r in self._conn.execute(
                    "SELECT * FROM episodes WHERE run_id = ? ORDER BY ts DESC LIMIT ?",
                    (run_id, limit),
                )
            ]
        for r in rows:
            r.pop("embedding", None)
        # Return oldest-first for reflection readability
        return list(reversed(rows))

    def count_episodes(self) -> int:
        with self._lock:
            (n,) = self._conn.execute("SELECT COUNT(*) FROM episodes").fetchone()
        return int(n)

    # ------------------------------------------------------------------
    # Insights
    # ------------------------------------------------------------------

    def insert_insight(
        self,
        *,
        text: str,
        tags: Sequence[str],
        embedding: Optional[np.ndarray],
        support_count: int = 1,
        ts: Optional[float] = None,
    ) -> int:
        ts = ts if ts is not None else time.time()
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO insights
                  (created_ts, last_reinforced_ts, support_count, tags, text, embedding)
                VALUES (?,?,?,?,?,?)
                """,
                (ts, ts, int(support_count), json.dumps(list(tags)), text, _blob(embedding)),
            )
            rid = int(cur.lastrowid)
            self._conn.commit()
        return rid

    def reinforce_insight(self, insight_id: int, ts: Optional[float] = None) -> None:
        ts = ts if ts is not None else time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE insights SET support_count = support_count + 1, last_reinforced_ts = ? WHERE id = ?",
                (ts, insight_id),
            )
            self._conn.commit()

    def fetch_insights(self, with_embeddings: bool = True) -> List[Dict[str, Any]]:
        with self._lock:
            rows = [
                dict(r)
                for r in self._conn.execute(
                    "SELECT * FROM insights ORDER BY last_reinforced_ts DESC"
                )
            ]
        for r in rows:
            try:
                r["tags"] = json.loads(r.get("tags") or "[]")
            except Exception:
                r["tags"] = []
            if with_embeddings:
                r["embedding"] = _unblob(r.get("embedding"))
            else:
                r.pop("embedding", None)
        return rows

    def count_insights(self) -> int:
        with self._lock:
            (n,) = self._conn.execute("SELECT COUNT(*) FROM insights").fetchone()
        return int(n)

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                (key, value),
            )
            self._conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.commit()
            finally:
                self._conn.close()
