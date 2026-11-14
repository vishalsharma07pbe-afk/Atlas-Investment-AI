# ATLAS AI provider failover (opt-in)

The provider-independent `app.ai_failover.analyze_market` accepts only a small allowlist of **public market indicators**, rejects unknown private fields and credential-like strings, and routes across explicitly enabled providers. This is **not** a live market-data source, autonomous trading agent, or guarantee of investment accuracy.

Default provider order: `OLLAMA,GEMINI,GROQ`. Set `ATLAS_AI_PROVIDER_ORDER` to any unique comma-separated subset of `OLLAMA,GEMINI,GROQ,OPENAI,XAI`.

- Ollama (local Llama): `ATLAS_OLLAMA_ENABLED=true`; service must listen on **127.0.0.1:11434** from the Python process. In Docker, loopback points to the container, so configure a local sidecar/network deployment before enabling. Model `ATLAS_OLLAMA_MODEL` defaults to `llama3.2`.
- Gemini: `ATLAS_EXTERNAL_AI_ALLOWED=true`, `ATLAS_GEMINI_ENABLED=true`, `GEMINI_API_KEY`, optional `ATLAS_GEMINI_MODEL`.
- Groq: `ATLAS_EXTERNAL_AI_ALLOWED=true`, `ATLAS_GROQ_ENABLED=true`, `GROQ_API_KEY`, optional `ATLAS_GROQ_MODEL`.
- OpenAI: `ATLAS_EXTERNAL_AI_ALLOWED=true`, `ATLAS_PAID_AI_ALLOWED=true`, `ATLAS_OPENAI_ENABLED=true`, `OPENAI_API_KEY`, optional `ATLAS_OPENAI_MODEL`.
- xAI Grok: `ATLAS_EXTERNAL_AI_ALLOWED=true`, `ATLAS_PAID_AI_ALLOWED=true`, `ATLAS_XAI_ENABLED=true`, `XAI_API_KEY`, optional `ATLAS_XAI_MODEL`.

Provider-specific free tiers and model names change; verify quotas and pricing before enabling. ChatGPT subscriptions do not imply API credits. Free-tier Gemini prompts may be used for provider model improvement; do not send confidential data. No secret should be committed. This module does not expose an unauthenticated public HTTP inference endpoint.
