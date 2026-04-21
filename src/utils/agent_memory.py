"""Back-compat shim. The real implementation lives in src/utils/memory/."""

from .memory import AgentMemory, MemoryStore  # noqa: F401

__all__ = ["AgentMemory", "MemoryStore"]
