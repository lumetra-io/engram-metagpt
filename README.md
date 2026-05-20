# engram-metagpt

[MetaGPT](https://github.com/FoundationAgents/MetaGPT) integration for [Engram](https://lumetra.io) — durable cross-run memory for multi-agent simulations.

MetaGPT's built-in `Memory` is per-process and dies when `Team.run()` returns. This recipe gives a role (or a whole team) a hosted Engram bucket they all share, with two integration surfaces designed to be used together:

1. **`EngramMemory(Memory)`** — drop-in replacement for `role.rc.memory`. Every observed message is mirrored to a single Engram bucket, so the next process picks up where the last one left off.
2. **`EngramStoreMemory` / `EngramQueryMemory` Actions** — first-class MetaGPT `Action` subclasses any role can list under `set_actions(...)`. The agent deliberately stores atomic facts and queries them via Engram's hybrid retrieval pipeline.

## Install

```bash
pip install -e .
export ENGRAM_API_KEY="eng_live_..."
```

(Recipe is local-install only — vendored alongside `engram-crewai`, `engram-camel-ai`, etc., not on PyPI.)

## Get an Engram API key

Sign up at <https://lumetra.io> — free tier, no card. You'll see an `eng_live_…` token in your dashboard.

**Don't forget BYOK** — Engram is bring-your-own-key end-to-end for the LLM that does extraction + synthesis. Configure a provider at <https://lumetra.io/models>. DeepSeek is what we recommend. Without one, store/query returns HTTP 412.

## MetaGPT config

MetaGPT loads `~/.metagpt/config2.yaml` at import time. For Anthropic:

```yaml
llm:
  api_type: "anthropic"
  api_key: "sk-ant-..."
  base_url: "https://api.anthropic.com"
  model: "claude-haiku-4-5-20251001"
  max_token: 1024
```

If you'd rather not write a global config, build a `Config` programmatically — see `example.py`.

## Usage — `EngramMemory` (passive transcript mirror)

```python
from metagpt.roles import Role
from engram_metagpt import EngramMemory

role = Role(name="Alice", profile="Analyst")
role.rc.memory = EngramMemory(bucket="my-team-transcript")
```

Now every `Message` the role observes is mirrored to the `my-team-transcript` bucket. MetaGPT's local `Memory` semantics (the `index`, `find_news`, `get_by_actions`) all keep working unchanged — Engram is a write-through mirror, not a replacement for the in-process buffer.

`try_remember(keyword)` falls back to Engram's hybrid retrieval if the local buffer has no hit, so the role can recall facts learned in an earlier process run.

## Usage — Engram Actions (deliberate memory)

```python
from engram_metagpt import engram_actions

role = Role(name="Researcher", profile="Analyst")
role.set_actions(engram_actions(bucket="my-team-facts"))
```

The role now has two actions available:

- `EngramStoreMemory` — `await action.run(content)` → saves one atomic fact, returns `"stored memory_id=..."`.
- `EngramQueryMemory` — `await action.run(query)` → returns the synthesized answer string from Engram's hybrid retrieval (BM25 + vector + knowledge graph fusion).

Combine them with other actions and MetaGPT's `react_mode="react"` to let the agent decide *when* to remember and recall on its own.

## Why this beats MetaGPT's built-in memory

- **Persists across runs.** MetaGPT's `Memory` is per-process; the next `Team.run()` starts blank. Engram doesn't.
- **Shared across roles.** Engram is the team's institutional memory, not a per-role scratchpad.
- **Hybrid retrieval** — BM25 + vector + knowledge graph fusion, not vector-only.
- **Bring-your-own-LLM** for extraction and synthesis (<https://lumetra.io/models>).
- **Per-team buckets** — pass `bucket=f"team-{project_id}"` and isolation is automatic.

## Verified

Smoke-tested against live `api.lumetra.io` with the Anthropic-backed MetaGPT provider (`claude-haiku-4-5-20251001`). The flow in `example.py`:

1. Build a `Role` with a custom `SummarizeUserFact` action.
2. Swap `EngramMemory(bucket=transcript_bucket)` into `role.rc.memory`.
3. Mirror a user message + an LLM-generated summary through Engram.
4. Invoke `EngramStoreMemory` twice (two atomic facts).
5. Invoke `EngramQueryMemory` against the facts bucket.

Cross-checked with curl — both facts landed in the bucket as expected, and the mirrored transcript bucket extracted the user/assistant content into atomic memories.

## License

MIT — Lumetra
