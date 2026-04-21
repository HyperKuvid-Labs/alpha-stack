"""Memory layer: retrieval-aware episodic + semantic store shared by planner
and orchestrator. See core.py for the public MemoryStore."""

from .core import MemoryStore

# Back-compat alias — old callers import AgentMemory.
AgentMemory = MemoryStore

__all__ = ["MemoryStore", "AgentMemory"]
