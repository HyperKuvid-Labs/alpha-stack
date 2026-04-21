# Memory Layer

Retrieval-aware episodic + semantic memory shared by the planner
(`src/testing/testing.py`) and the orchestrator (`src/orchestrator.py` +
`src/generator.py`). Replaces the previous flat append-only log
(`src/utils/agent_memory.py`), which concatenated the entire history into
every prompt and collapsed older entries with a blocking LLM summarization.

---

## Why the rewrite

The old memory had three structural problems:

1. **Whole-log injection.** Every planner round dumped the full buffer into
   the prompt. Context scaled linearly with iteration count; there was no
   notion of "what's relevant to *this* failure."
2. **Lossy, synchronous compaction.** Crossing ~30k tokens triggered an
   inline LLM summarization that blocked tool dispatch and collapsed
   per-entry structure into prose.
3. **Monotonically growing cross-run blob.** `load()` concatenated last
   run's `previous_summary + summaries + entries` into a single
   `_previous_summary` string that was never re-digested.

In addition, planner and orchestrator each kept an isolated memory, so
lessons learned during generation never reached the test-fixing planner.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      MemoryStore (core.py)                 │
│                                                            │
│   Working buffer         ┌─────────────────────────────┐   │
│   (last K=15 entries) ───┤  render(query, budget)      │   │
│                          │    1. Working                │   │
│   LoopDetector          │    2. Lessons (insights)    │   │
│   (dedup.py) ────────────┤    3. Similar (episodes)    │   │
│                          │    4. LoopWarn              │   │
│                          └─────────────────────────────┘   │
│                                                            │
│   ┌──────────────┐   ┌──────────────┐   ┌────────────────┐ │
│   │ episodes     │   │ insights     │   │ meta           │ │
│   │  +embedding  │   │  +embedding  │   │  schema, runs  │ │
│   └──────────────┘   └──────────────┘   └────────────────┘ │
│          SQLite at .alpha_stack/memory.db                  │
│                                                            │
│   ReflectionWorker (reflect.py, daemon thread)             │
│     ├─ trigger: test pass → distill the winning fix        │
│     ├─ trigger: 60s quiet after FAIL → distill the miss    │
│     └─ trigger: session end on save()                      │
│          writes to insights; cosine-dedup ≥ 0.92           │
└────────────────────────────────────────────────────────────┘
```

Both planner and orchestrator share one store per project. Role is stored
on each row so views can filter, but the knowledge pool is unified.

---

## Module layout (`src/utils/memory/`)

| File             | Role                                                                              |
|------------------|-----------------------------------------------------------------------------------|
| `core.py`        | `MemoryStore` facade — preserves the old `AgentMemory` API                        |
| `store.py`       | SQLite DAO: `episodes`, `insights`, `meta`                                        |
| `embed.py`       | Lazy embedder: sentence-transformers MiniLM (384-dim) + hashed fallback           |
| `retrieval.py`   | `score_and_topk` — α·relevance + β·importance + γ·recency                         |
| `reflect.py`     | Daemon-thread Reflexion worker, strict-JSON LLM calls, cosine-dedup               |
| `dedup.py`       | `LoopDetector` — sliding-window signature hashing, threshold-based LoopWarn       |
| `signatures.py`  | `normalize_error`, `error_signature` → `(class, 12-char hash)`                    |
| `__init__.py`    | Re-exports `MemoryStore` and an `AgentMemory` alias                               |

`src/utils/agent_memory.py` is now a three-line shim that re-exports the new
class, so the existing `from .utils.agent_memory import AgentMemory` imports
keep working unchanged.

---

## Public API (preserved)

`MemoryStore` keeps the full surface the old `AgentMemory` exposed:

```python
record(session, action, file, detail, outcome)
record_edit(session, file_path, description)
record_batch_edit(session, tasks)
record_shell(session, command, output, success)
record_guidance(filepath, summary)
record_regenerate(filepath, corrections)
save(path=None)          # path ignored; persistence is the SQLite file
load(path=None)          # no-op; DB opens lazily
render(query=None, budget_tokens=2000, role=None) -> str
__len__, __bool__
```

Two additions:

- `render(query=...)` — when supplied, composes a multi-section prompt using
  retrieval; without a query, falls back to recency-ordered rendering.
- Constructor now accepts `project_root` + `role`. No args still works
  (in-memory mode, matches the orchestrator's prior default).

---

## Storage schema

```sql
episodes(
  id, run_id, role, ts, session,
  action, file, detail, outcome,
  importance, error_class, error_hash,
  embedding BLOB           -- float32[384]
)

insights(
  id, created_ts, last_reinforced_ts,
  support_count, tags, text,
  embedding BLOB
)

meta(key PRIMARY KEY, value)
```

Writes to SQLite are synchronous; the in-memory numpy matrix is rebuilt on
open from the `embedding` BLOBs (cheap — fewer than ~10k rows per project).
FAISS is listed as an optional dep but flat cosine-scoring in numpy is
sub-millisecond at these scales, so the hot path doesn't depend on it.

**Importance score** (heuristic, computed at `record()`):

| Event                                         | Importance |
|-----------------------------------------------|-----------:|
| shell FAIL                                    | 0.9        |
| shell OK after a recent FAIL on same class    | 1.0        |
| edit / batch_edit                             | 0.8        |
| regenerate                                    | 0.7        |
| guidance                                      | 0.5        |
| other / routine                               | 0.3        |

---

## Retrieval

```
score = 0.5 · cos(query, emb) + 0.3 · importance + 0.2 · exp(-Δt / τ)
τ = 6 hours
```

Weights follow Park et al. (Generative Agents): relevance-heavy, recency as
a tie-breaker. For the planner, the query is `state.last_test_output`. For
the orchestrator, it's the child agent's question (or a concatenation when
batched).

`render()` composes four token-budgeted sections (in priority order —
lower-priority sections truncate first):

| Section    | Source                                                 | Cap      |
|------------|--------------------------------------------------------|----------|
| Working    | last K=15 full-detail entries                          | 800 tok  |
| Lessons    | top-5 matched insights (tag-overlap, then semantic)    | 400 tok  |
| Similar    | top-8 retrieved episodes (7-day recency filter)        | 600 tok  |
| LoopWarn   | repeated-action warnings from `LoopDetector`           | 200 tok  |

An overall `budget_tokens` (default 2000) hard-caps the combined output.

---

## Reflection worker

A daemon thread owns a bounded `queue.Queue` of `ReflectionTask`s. Triggers:

1. **Success** — planner emits `tests_passed`; the worker pulls the last 30
   episodes and asks the LLM to distill the fix that worked.
2. **Quiet fail** — shell FAIL with no new records in 60s; the worker asks
   the LLM to name the wrong assumption.
3. **Session end** — `save()` enqueues a final reflection, then stops the
   thread with a 3s join timeout.

The LLM is called via `InferenceManager.get_active_provider()` (same path
the old compactor used) with a strict-JSON prompt:

```json
[{"text": "<one-sentence lesson>",
  "tags": ["<language|tool|error_class>"],
  "supports_episode_ids": [<int>]}]
```

Each parsed insight is embedded and compared against existing insights by
cosine similarity. At ≥ 0.92 it reinforces (increments `support_count` +
bumps `last_reinforced_ts`); otherwise it's inserted as a new row. Failures
are swallowed — the worker never blocks `record()`.

---

## Loop / duplicate detector

Signature: `md5(action | file | normalize(detail))[:10]`, where
`normalize` lowercases, collapses whitespace, and replaces digits with
`<N>`. A deque of the last 50 signatures is kept. Once a signature fires
three or more times in the window, `render()` surfaces a `LoopWarn` like:

```
⚠ tried edit loopy.py 3× already — last outcome: FAIL
```

The planner sees this in-context next round, which short-circuits
repeated-identical-fix loops.

---

## Legacy migration

On first open against a project that has an old `planner_memory.json`:

1. If the DB already has rows for this project → skip.
2. Otherwise walk `entries[]` and call the normal insert path (with
   `importance=0.3`, batched embeddings).
3. Roll `previous_summary + summaries` into a single bootstrap insight
   tagged `["legacy"]`.
4. Rename the JSON to `.imported` so it's clear but recoverable.

The `meta` table records `legacy_imported=1` so re-opens don't re-import.

---

## Call-site changes

| File                                | Change                                                                             |
|-------------------------------------|------------------------------------------------------------------------------------|
| `src/testing/testing.py`            | `AgentMemory(project_root=..., role="planner")`; `render(query=last_test_output)`; `notify_success()` on pass; `save()` with no path |
| `src/generator.py`                  | Both single and batch orchestrator paths pass `query` (child question / joined)    |
| `src/orchestrator.py`               | `AgentMemory(project_root=output_base_dir, role="orchestrator")`; `save()` at end of `execute()` (fix: the orchestrator never saved before) |
| `src/prompts/planner_pipeline.j2`   | Memory block heading updated (the rendered string carries its own section headers) |
| `src/prompts/orchestrator_agent.j2` | Same heading update                                                                |
| `src/utils/agent_memory.py`         | Reduced to a 3-line re-export shim                                                 |

---

## Dependencies

Added to `pyproject.toml`:

- `numpy>=1.24` — required (cosine scoring + blob packing)
- `[project.optional-dependencies].memory`:
  - `sentence-transformers>=3.0.0`
  - `faiss-cpu>=1.8.0`

If `sentence-transformers` is missing or import fails (e.g. air-gapped
env), the embedder transparently falls back to a deterministic hashed
term-vector embedder with the same interface. Retrieval quality degrades
gracefully; nothing crashes. The fallback can also be forced with
`ALPHASTACK_EMBED_BACKEND=hash` — used by the test suite so CI doesn't
download the model.

---

## Tests

`tests/test_memory.py` (10 tests):

- record → retrieve round-trip
- render without a query falls back to recency
- persistence across close + reopen
- loop detector surfaces a warning after 3× repeat
- legacy JSON import: episodes inserted + file renamed
- token-budget enforcement
- reflection (mocked provider): insight written with expected tags
- reflection dedup: identical lesson reinforces instead of duplicating
- `from src.utils.agent_memory import AgentMemory` back-compat
- in-memory (no `project_root`) constructor still works

Full suite: **80 passed, 0 regressions** (`pytest -q`).

---

## Papers referenced

The design leans on four pieces of prior work. Each informed a specific
architectural decision rather than being cargo-culted:

### 1. Reflexion — Shinn et al., NeurIPS 2023
*"Reflexion: Language Agents with Verbal Reinforcement Learning"*
→ <https://arxiv.org/abs/2303.11366>

**Used for:** The reflection worker. Rather than gradient updates,
Reflexion shows that letting an agent *verbally* critique its own
trajectory after success/failure and storing those critiques as durable
lessons produces large downstream gains on code and reasoning tasks. Our
`reflect.py` mirrors this: episodes → LLM critique → structured insights
that survive across runs and are retrieved by the next attempt.

### 2. Generative Agents — Park et al., UIST 2023
*"Generative Agents: Interactive Simulacra of Human Behavior"*
→ <https://arxiv.org/abs/2304.03442>

**Used for:** The retrieval scoring function. Their simulation uses
`score = α·recency + β·importance + γ·relevance` with relevance-heavy
weights to pick which memories surface in an agent's context. We adopted
the same three-term composition
(`0.5·relevance + 0.3·importance + 0.2·recency`, τ = 6h) in
`retrieval.score_and_topk`.

### 3. MemGPT — Packer et al., 2023
*"MemGPT: Towards LLMs as Operating Systems"*
→ <https://arxiv.org/abs/2310.08560>

**Used for:** The hybrid working-buffer + retrieved-long-term-memory
layout. MemGPT treats the context window as RAM with explicit paging
between a small always-in-context working set and retrieved external
storage. Our render path does the same: the last K=15 entries always
appear verbatim (working buffer), while deeper history is retrieved only
when relevant to the current query.

### 4. CoALA — Sumers et al., 2024
*"Cognitive Architectures for Language Agents"*
→ <https://arxiv.org/abs/2309.02427>

**Used for:** The episodic / semantic split. CoALA argues language agents
need distinct memory types: episodic (specific experiences) vs. semantic
(generalized knowledge). Our two tables map onto this: `episodes` holds
raw action traces (episodic); `insights` holds reflection-distilled
lessons (semantic). Retrieval considers both, scored separately.

### Explicitly out of scope

- **Voyager** (Wang et al., 2023) — a procedural skill library would
  promote frequently-reinforced insights into callable skills. The
  `insights` table is the foundation but no promotion step exists yet.
- **HippoRAG** (Gutiérrez et al., 2024) — graph-based retrieval. Flat
  FAISS / numpy cosine is sufficient at current scales (< 10k episodes
  per project).
- **Cross-project memory** — the store is deliberately per-project to
  avoid context pollution between unrelated codebases.
