"""MetaGPT `Action` subclasses for deliberate Engram memory writes/reads.

Drop these into any role's `set_actions(...)` list and the role can
choose to store an atomic fact, or query its shared bucket, the same way
it would call any other tool-style Action.

These actions wrap the synchronous `EngramClient` and run in a thread
via `asyncio.to_thread` so they cooperate with MetaGPT's async loop
without blocking the event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from pydantic import ConfigDict, PrivateAttr

from metagpt.actions import Action

from engram_metagpt.client import EngramClient, extract_final_answer


class _BaseEngramAction(Action):
    """Shared scaffolding for store/query Engram actions.

    Each instance holds an `EngramClient` and a target bucket. The
    client is resolved lazily from env if not passed explicitly.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    bucket: str = "metagpt-actions"
    _client: Optional[EngramClient] = PrivateAttr(default=None)

    def __init__(
        self,
        bucket: str = "metagpt-actions",
        *,
        client: Optional[EngramClient] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **data: Any,
    ) -> None:
        super().__init__(bucket=bucket, **data)
        self._client = client or EngramClient(api_key=api_key, base_url=base_url)


class EngramStoreMemory(_BaseEngramAction):
    """Save an atomic fact to the shared Engram bucket.

    `await action.run(content)` returns the new `memory_id` as a string,
    so the caller can include it in a `Message` if useful.
    """

    name: str = "EngramStoreMemory"

    async def run(self, content: str, **_: Any) -> str:  # type: ignore[override]
        if not content:
            return "stored memory_id=(empty content, skipped)"
        result = await asyncio.to_thread(
            self._client.store_memory, content, self.bucket
        )
        memory_id = result.get("memory_id") or result.get("id") or "(unknown)"
        return f"stored memory_id={memory_id}"


class EngramQueryMemory(_BaseEngramAction):
    """Hybrid retrieval + synthesized answer over the shared bucket.

    `await action.run(query)` returns the final synthesized answer
    string (with Engram's reasoning prefix stripped), or a
    ``"No relevant memories found."`` sentinel on empty results.
    """

    name: str = "EngramQueryMemory"

    async def run(self, query: str, **_: Any) -> str:  # type: ignore[override]
        if not query:
            return "No relevant memories found."
        result = await asyncio.to_thread(
            self._client.query, query, self.bucket
        )
        answer = extract_final_answer(result.get("answer") or "")
        return answer or "No relevant memories found."


def engram_actions(
    bucket: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    client: Optional[EngramClient] = None,
) -> List[Action]:
    """Return a `[EngramStoreMemory, EngramQueryMemory]` pair wired to one
    bucket. Pass to `role.set_actions([...])` or include in a list of
    other actions.
    """
    c = client or EngramClient(api_key=api_key, base_url=base_url)
    return [
        EngramStoreMemory(bucket=bucket, client=c),
        EngramQueryMemory(bucket=bucket, client=c),
    ]
