"""
engram_metagpt — durable cross-run memory for MetaGPT.

MetaGPT's built-in `Memory` is an in-process list of `Message` objects
that dies when the process exits. This recipe gives a MetaGPT role (or a
whole team) a hosted Engram bucket they all share, with two integration
surfaces designed to be used together:

1. **`EngramMemory(Memory)`** — drop-in replacement for the per-role
   `Memory`. Every `add()` mirrors the message content through to a
   single Engram bucket via the REST API. `try_remember(keyword)` falls
   back to Engram's hybrid retrieval when the local in-process buffer
   doesn't have a hit, so a role can recall facts it learned in a prior
   process run. Useful for cross-`Team.run()` continuity without
   touching role business logic.

2. **`EngramStoreMemory` / `EngramQueryMemory` Actions** — first-class
   MetaGPT `Action` subclasses that any role can list under `actions=`.
   When the role's `_act` triggers one of these, it executes a single
   store-fact / query-memory call against Engram and returns the result
   as a `Message`. This gives the agent *deliberate* memory writes,
   distinct from passive transcript persistence.

Both layers use the Engram REST API (https://api.lumetra.io) and the
same `ENGRAM_API_KEY` env var.

Quick start:

    from metagpt.roles import Role
    from engram_metagpt import EngramMemory, engram_actions

    role = Role(name="Alice", profile="Analyst")
    role.rc.memory = EngramMemory(bucket="my-team")  # passive transcript
    role.set_actions(engram_actions(bucket="my-team-facts"))  # active recall
"""

from __future__ import annotations

from engram_metagpt.client import EngramClient
from engram_metagpt.memory import EngramMemory
from engram_metagpt.actions import (
    EngramStoreMemory,
    EngramQueryMemory,
    engram_actions,
)

__all__ = [
    "EngramClient",
    "EngramMemory",
    "EngramStoreMemory",
    "EngramQueryMemory",
    "engram_actions",
]

__version__ = "0.1.0"
