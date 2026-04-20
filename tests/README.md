# alphastack tests

Stage-by-stage pipeline tests. The design goal is **minimal LLM dependency**:
almost every test runs offline. The only tests that touch a real model are
tagged `@pytest.mark.llm` and skipped by default — they're opt-in via
`pytest -m llm`.

## Run

```bash
# Fast, hermetic — no network, no LLM. Runs in under a few seconds.
pytest tests/

# Include the LLM-backed tests (requires OPENROUTER_API_KEY or similar).
pytest tests/ -m "llm or not llm"

# Just the LLM tests:
pytest tests/ -m llm
```

## Layout

- `tests/conftest.py` — fixtures (fake LLM provider, dep-analyzer fixture).
- `tests/test_config.py` — provider mapping, api-key resolution, dgat sync.
- `tests/test_json_extractor.py` — the blueprint JSON extractor corner cases.
- `tests/test_prompt_manager.py` — Jinja template rendering.
- `tests/test_tree_parser.py` — `generate_tree` on many folder-structure shapes.
- `tests/test_dependency_analyzer.py` — dgat adapter (runs `dgat --deps-only`, no LLM).
- `tests/test_tool_handler.py` — all tool handlers exposed to agents.
- `tests/test_inference.py` — provider registry, model override, key lookup.
- `tests/test_blueprint_parsing.py` — blueprint JSON parsing via a **fake** LLM.
- `tests/test_ping_rpc.py` — `_rpc_ping_model` using the fake LLM.
- `tests/test_live_blueprint.py` — `@pytest.mark.llm` real blueprint call (opt-in).

## Philosophy

- Tests must be **fast**. Target < 5s for the default suite.
- No test depends on a real model response unless explicitly marked `llm`.
- Fake provider supplies canned JSON/text so pipeline logic is exercised
  without real API traffic.
- dgat tests use `DGAT_DEPS_ONLY=1` which skips description generation —
  tree-sitter only, no LLM.
