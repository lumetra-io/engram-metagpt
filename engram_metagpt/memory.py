"""`EngramMemory` — drop-in `metagpt.memory.Memory` backed by Engram.

MetaGPT's `Memory` is an in-process Pydantic model: `storage: list[Message]`
plus an `index: dict[cause_by, list[Message]]`. It dies with the process.

`EngramMemory` keeps that exact local behavior (so MetaGPT's role loop,
indexing, and `find_news` all keep working unchanged) and *additionally*
mirrors every `add()` to a hosted Engram bucket. When `try_remember()` is
called and the local buffer has no hit, it falls back to Engram's hybrid
retrieval — letting a role recall facts learned in a previous process run.

Usage:

    role.rc.memory = EngramMemory(bucket="my-team")
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import ConfigDict, PrivateAttr

from metagpt.memory import Memory
from metagpt.schema import Message

from engram_metagpt.client import EngramClient, extract_final_answer


class EngramMemory(Memory):
    """Durable `Memory` backed by an Engram bucket.

    `add()`: appends to the local buffer (preserving MetaGPT's index +
        find_news semantics) **and** mirrors the message content to
        Engram so it survives process restarts.

    `try_remember(keyword)`: returns local matches first; if none, falls
        back to a hybrid retrieval call against Engram and surfaces the
        synthesized answer as a single virtual `Message` (role=
        ``"engram"``). This is best-effort; if the network or key is
        missing it returns the empty local result.

    `clear()`: clears local state and the underlying Engram bucket.
    """

    # Allow arbitrary attrs (the client) on the pydantic model.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    bucket: str = "metagpt-memory"
    mirror_role: bool = True  # include role/cause_by in mirrored content
    _client: Optional[EngramClient] = PrivateAttr(default=None)

    def __init__(
        self,
        bucket: str = "metagpt-memory",
        *,
        client: Optional[EngramClient] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        mirror_role: bool = True,
        **data: Any,
    ) -> None:
        super().__init__(bucket=bucket, mirror_role=mirror_role, **data)
        self._client = client or EngramClient(api_key=api_key, base_url=base_url)

    # ------------------------------------------------------------------ #
    # write path                                                         #
    # ------------------------------------------------------------------ #

    def _format_for_engram(self, message: Message) -> str:
        if not self.mirror_role:
            return message.content
        prefix_parts: List[str] = []
        role = getattr(message, "role", None)
        if role:
            prefix_parts.append(f"role={role}")
        cause_by = getattr(message, "cause_by", None)
        if cause_by:
            prefix_parts.append(f"cause_by={cause_by}")
        prefix = " ".join(prefix_parts)
        return f"[{prefix}] {message.content}" if prefix else message.content

    def add(self, message: Message) -> None:
        # Run MetaGPT's local bookkeeping first so role.rc loops are
        # unaffected even if the network call below blocks or fails.
        prev_count = len(self.storage)
        super().add(message)
        if len(self.storage) == prev_count:
            # Duplicate; super().add returned early. Don't mirror.
            return
        if not message.content:
            return
        try:
            self._client.store_memory(
                self._format_for_engram(message), self.bucket
            )
        except Exception:
            # Best-effort mirror. Never let a transient REST failure
            # break the agent loop.
            pass

    # ------------------------------------------------------------------ #
    # read path                                                          #
    # ------------------------------------------------------------------ #

    def try_remember(self, keyword: str) -> List[Message]:
        local = super().try_remember(keyword)
        if local:
            return local
        try:
            result = self._client.query(keyword, bucket=self.bucket)
        except Exception:
            return []
        answer = extract_final_answer(result.get("answer") or "")
        if not answer or answer.lower().startswith("no relevant"):
            return []
        return [Message(content=answer, role="engram")]

    # ------------------------------------------------------------------ #
    # destructive                                                        #
    # ------------------------------------------------------------------ #

    def clear(self) -> None:
        super().clear()
        try:
            self._client.clear_memories(self.bucket)
        except Exception:
            pass
