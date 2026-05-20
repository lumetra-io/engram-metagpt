# Privacy

This recipe sends the parameters you (or your MetaGPT role) pass to its memory surfaces — `content`, `query`, `bucket`, `memory_id` — to the Engram REST API at `https://api.lumetra.io` (or the self-hosted base URL you configured via `ENGRAM_BASE_URL`). Memories are stored under your Engram tenant, scoped by the API key you provided in `ENGRAM_API_KEY`.

When you swap `EngramMemory` into `role.rc.memory`, the full text of each `Message` your role observes is mirrored to Engram. If you don't want passive mirroring, use the `EngramStoreMemory` / `EngramQueryMemory` Actions instead — those only send content the agent explicitly chose to store or query.

The recipe does not collect, log, or transmit data to any third party other than the Engram service you've explicitly authorized. It does not read other MetaGPT artifacts (workspaces, generated code, project repos) — only the parameters supplied to each memory call.

For Engram's own data-handling and retention policy, see <https://lumetra.io/privacy>.
