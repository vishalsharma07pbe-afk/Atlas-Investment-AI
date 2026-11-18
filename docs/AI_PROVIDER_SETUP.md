# ATLAS AI provider setup

ATLAS supports a local Ollama model plus Google Gemini, Groq-hosted models,
OpenAI API models, and xAI Grok. The browser never receives provider keys. An
authenticated browser request goes to Spring, then crosses a shared-token
internal bridge to the intelligence service.

## 1. Enable the internal bridge

```sh
./scripts/configure-local-ai-bridge.sh
```

This generates a random internal token in the ignored local `.env` and enables
the backend proxy. It does not enable any model provider.

## 2. Choose providers in `.env`

Edit `.env` locally. Never paste API keys into chat, screenshots, source files,
or the browser UI. Start with low request budgets and only raise them after
checking the provider's current pricing and account limits.

### Ollama (local)

Install Ollama on the host, pull the selected model, and confirm its API is
listening on port 11434. Then set:

```dotenv
ATLAS_OLLAMA_ENABLED=true
ATLAS_OLLAMA_URL=http://host.docker.internal:11434
ATLAS_OLLAMA_MODEL=llama3.2
```

Only explicitly allowlisted local Ollama addresses are accepted.

### Gemini

```dotenv
ATLAS_EXTERNAL_AI_ALLOWED=true
ATLAS_GEMINI_ENABLED=true
GEMINI_API_KEY=your_local_key
ATLAS_GEMINI_MODEL=gemini-3.5-flash-lite
```

### Groq

```dotenv
ATLAS_EXTERNAL_AI_ALLOWED=true
ATLAS_GROQ_ENABLED=true
GROQ_API_KEY=your_local_key
```

### OpenAI API

A ChatGPT subscription is separate from OpenAI API access. Configure an API
key and explicitly allow paid providers, then set nonzero limits:

```dotenv
ATLAS_EXTERNAL_AI_ALLOWED=true
ATLAS_PAID_AI_ALLOWED=true
ATLAS_OPENAI_ENABLED=true
OPENAI_API_KEY=your_local_key
ATLAS_OPENAI_RPM=2
ATLAS_OPENAI_RPD=20
```

### xAI Grok

```dotenv
ATLAS_EXTERNAL_AI_ALLOWED=true
ATLAS_PAID_AI_ALLOWED=true
ATLAS_XAI_ENABLED=true
XAI_API_KEY=your_local_key
ATLAS_XAI_RPM=2
ATLAS_XAI_RPD=20
```

Models and provider order are configurable with `ATLAS_<PROVIDER>_MODEL` and
`ATLAS_AI_PROVIDER_ORDER`. Confirm current model availability in the provider's
official documentation before changing a model name.

## 3. Apply and verify

```sh
docker compose up -d --build backend intelligence frontend
docker compose run --rm --no-deps -v ./intelligence/tests:/app/tests:ro intelligence \
  python -m unittest discover -s tests -p 'test_ai*.py'
```

Open **Stock Explorer → AI Committee**. Provider health uses these states:

- `READY_TO_CALL`: configuration is complete, but no successful response is implied.
- `API_KEY_REQUIRED`, `EXTERNAL_OPT_IN_REQUIRED`, or `PAID_OPT_IN_REQUIRED`: an explicit local setting is missing.
- `BUDGET_DISABLED` or `INVALID_BUDGET`: request limits prevent calls.
- `DISABLED`: the provider toggle is off.

A provider is only marked `connection_verified` after an analysis returns that
provider's validated structured result. The timestamp is process-local and
resets when the intelligence service restarts. Model output is research
commentary, not verified market data or investment advice.
