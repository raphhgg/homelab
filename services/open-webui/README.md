# Open WebUI Service

This service provides the Open WebUI interface for interacting with Ollama models.

## Configuration

Before deploying, you need to:
1. Create a `.env` file in this directory based on `.env.example`
2. Update `OLLAMA_BASE_URL` to point to your Ubuntu server's Ollama instance (e.g., `http://192.168.1.100:11434`)

## Deployment

```bash
cd services/open-webui
docker-compose up -d
```

## Access

The web interface will be available at:
- http://localhost:8080 (if running locally)
- Or the appropriate IP address/port for your server

## Integration with Ollama

The service connects to Ollama models running on a separate server by setting the `OLLAMA_BASE_URL` environment variable. This allows you to:
- Use local Ollama models from your Ubuntu server
- Access models via the web interface
- Have a user-friendly frontend for interacting with your AI models