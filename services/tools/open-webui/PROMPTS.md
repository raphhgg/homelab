# Gemma Prompt Guide

This Open WebUI setup uses two `llama-server` model presets:

- `gemma-4-chat`
- `gemma-4-research`

Open WebUI-side prompts are used for tone and behavior, not runtime tuning.

## Recommended Pairings

- `gemma-4-chat` + `Gemma Chat Style`
- `gemma-4-research` + `Gemma Research Style`

## Prompts

### Gemma Chat Style

Best for:

- everyday assistant use
- general questions
- brainstorming
- explanations
- personal productivity
- normal chatbot conversations

Use when:

- you want natural, friendly prose
- you do not need a highly structured or evidence-heavy answer

### Gemma Research Style

Best for:

- web search sessions
- fact-finding
- product comparisons
- current-events questions
- source-based summaries

Use when:

- you want the model to synthesize sources
- you care about uncertainty, evidence, and clear sourcing behavior

### Gemma Calm Style

Best for:

- longer conversations
- reflective discussion
- advice
- writing help
- nuanced or sensitive topics

Use when:

- the default chat prompt feels too brisk
- you want a more thoughtful and measured tone

### Gemma Analyst Style

Best for:

- technical topics
- system design
- tradeoff analysis
- debugging
- decision-making

Use when:

- you want precision and structure
- you want clearer distinctions between facts, interpretation, and uncertainty

## Quick Rule

- daily assistant: `Gemma Chat Style`
- search and sources: `Gemma Research Style`
- thoughtful tone: `Gemma Calm Style`
- technical rigor: `Gemma Analyst Style`
