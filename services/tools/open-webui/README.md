# Open WebUI Service

This service provides the Open WebUI interface for interacting with the local Qwen model served by llama.cpp.

## Configuration

Before deploying, you need to:
1. Create a `.env` file in this directory based on `.env.example`
2. Review `OLLAMA_BASE_URL` only if you want to enable Ollama as a secondary provider
3. Review any DNS overrides in `.env` if your stack relies on an internal resolver

## Deployment

```bash
cd services/tools/open-webui
docker compose up -d
```

## Access

The web interface will be available at:
- http://localhost:8087 (if running locally)
- Or the appropriate IP address/port for your server

## Integration with the local Qwen server

The service connects to the host's OpenAI-compatible llama.cpp endpoint through
`http://host.docker.internal:8081/v1`. The Qwen model is selected and pinned by
default, with native tool calling and automatic context compaction enabled.

Web search is enabled through Tavily with a confirmation prompt, and new chats
start with Web Search enabled by default. The native code interpreter uses the
browser-side Pyodide sandbox. The Qwen model is marked as text-only: vision
remains disabled until a vision-capable model and projector are deployed.

An admin-configured Open Terminal connection named `llm-workspace` is available
for coding workflows and is selected by default in new chats. It mounts only
`/home/raphh/llm-workspace` at
`/home/user/workspace` inside a private Docker network. The terminal has no
published port, no Docker socket, no GPU access, no outbound network by default,
and is limited to 2 CPUs, 2 GiB of memory, and 512 processes.

The global model metadata carries these defaults (`defaultFeatureIds:
['web_search']` and `terminalId: 'llm-workspace'`) so they apply to models
discovered from the OpenAI-compatible llama.cpp provider as well as saved model
profiles. Both features remain user-toggleable per chat.

The Ollama URL remains available as an optional secondary provider for other
models; it is not the default connection.
