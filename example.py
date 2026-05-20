"""End-to-end smoke test for engram_metagpt.

Drives a MetaGPT role with the Anthropic provider and exercises both
integration surfaces:

  1. `EngramMemory(Memory)` swapped into `role.rc.memory` — every message
     the role observes is mirrored through to a hosted Engram bucket.

  2. `EngramStoreMemory` / `EngramQueryMemory` Actions — invoked directly
     against the live Engram REST API, simulating what a role with these
     in `set_actions(...)` would do when its `_act` step picks them.

Run with:

    export ENGRAM_API_KEY=eng_live_...
    export ANTHROPIC_API_KEY=sk-ant-...
    python example.py

You also need a MetaGPT config at `~/.metagpt/config2.yaml` that points
the `llm` block at Anthropic — see README.md.
"""

from __future__ import annotations

import asyncio
import os
import uuid

from metagpt.actions import Action
from metagpt.config2 import Config
from metagpt.context import Context
from metagpt.roles import Role
from metagpt.schema import Message

from engram_metagpt import (
    EngramMemory,
    EngramStoreMemory,
    EngramQueryMemory,
)


class SummarizeUserFact(Action):
    """Tiny custom action: ask the LLM to restate the user's fact in one
    crisp sentence so we have something to mirror into Engram via the
    role's `rc.memory.add()` write path."""

    name: str = "SummarizeUserFact"

    async def run(self, fact: str, **_) -> str:  # type: ignore[override]
        prompt = (
            "Restate the following fact about the user as a single, "
            "first-person, declarative sentence under 20 words. "
            "Return only that sentence, no preamble.\n\n"
            f"Fact: {fact}"
        )
        return await self._aask(prompt)


async def main() -> None:
    run_id = uuid.uuid4().hex[:8]
    transcript_bucket = f"metagpt-smoke-transcript-{run_id}"
    facts_bucket = f"metagpt-smoke-facts-{run_id}"
    print(f"[example] transcript bucket: {transcript_bucket}")
    print(f"[example] facts      bucket: {facts_bucket}")

    # ----- 1. Configure MetaGPT with the Anthropic provider --------------
    # We build a Config explicitly so this example doesn't depend on a
    # user's global `~/.metagpt/config2.yaml`.
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        raise SystemExit("ANTHROPIC_API_KEY not set")

    llm_config = {
        "api_type": "anthropic",
        "api_key": anthropic_key,
        "base_url": "https://api.anthropic.com",
        "model": "claude-haiku-4-5-20251001",
        "max_token": 1024,
    }
    cfg = Config.from_llm_config(llm_config)
    ctx = Context(config=cfg)

    # ----- 2. Build a role with our custom action ------------------------
    role = Role(name="Alice", profile="Analyst", context=ctx)
    role.set_actions([SummarizeUserFact])

    # Swap in EngramMemory so every observed Message is mirrored.
    role.rc.memory = EngramMemory(bucket=transcript_bucket)

    # ----- 3. Drive the role's action manually ---------------------------
    user_fact = (
        "I'm Jacob Davis, co-founder of Lumetra. We're building Engram, "
        "a durable memory layer for AI agents."
    )
    print(f"\n[user] {user_fact}")

    # Mirror the user message through Engram.
    role.rc.memory.add(Message(content=user_fact, role="user"))

    # Run the custom action via the role's LLM.
    summary = await role.actions[0].run(user_fact)
    print(f"[assistant summary] {summary}")

    # Mirror the assistant summary too.
    role.rc.memory.add(Message(content=summary, role="assistant"))

    # ----- 4. Exercise the Engram Actions directly -----------------------
    store = EngramStoreMemory(bucket=facts_bucket)
    query = EngramQueryMemory(bucket=facts_bucket)

    store_result = await store.run(content=summary)
    print(f"[action] EngramStoreMemory -> {store_result}")

    # A second atomic fact, so the synthesizer has something to fuse.
    second = "Lumetra is headquartered in Seattle, Washington."
    print(f"[action] storing second fact: {second}")
    print(f"[action] EngramStoreMemory -> {await store.run(content=second)}")

    print("\n[action] querying Engram for 'where is Lumetra based?'")
    answer = await query.run(query="where is Lumetra based?")
    print(f"[action] EngramQueryMemory -> {answer}")

    # ----- 5. Verify the transcript bucket has the mirrored messages -----
    transcript = role.rc.memory._client.list_memories(
        transcript_bucket, limit=10
    )
    items = transcript.get("memories") or transcript.get("data") or []
    print(
        f"\n[example] transcript bucket holds {len(items)} mirrored "
        f"message(s) (expected >= 2)"
    )

    print("\n[example] cross-check with curl:")
    base = os.environ.get("ENGRAM_BASE_URL", "https://api.lumetra.io")
    print(
        f'  curl -s -H "Authorization: Bearer $ENGRAM_API_KEY" '
        f"{base}/v1/buckets/{facts_bucket}/memories?limit=10"
    )


if __name__ == "__main__":
    asyncio.run(main())
