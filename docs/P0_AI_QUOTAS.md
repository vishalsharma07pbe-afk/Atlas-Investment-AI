# P0 AI request budget manager

ATLAS now reserves a provider request in a persistent local SQLite ledger before making any AI call. The same provider is skipped when its minute or UTC-day budget is exhausted; the next enabled provider is tried. Failed requests still consume a reservation to avoid retry storms. Budget rows contain **only provider, window, and count**, never credentials, prompts or model responses.

Configurable per provider: `ATLAS_<PROVIDER>_RPM` and `ATLAS_<PROVIDER>_RPD`. Conservative starting defaults (not official provider quotas): OLLAMA 120/10000, GEMINI 2/30, GROQ 5/100, OPENAI 0/0, XAI 0/0. Paid providers require both existing paid opt-in and nonzero configured budgets. The local database defaults to `/app/ingestion-data/ai_budgets.sqlite3`; override `ATLAS_AI_BUDGET_DB_PATH` when running outside Docker.

These limits count **requests**, not tokens, spend, or provider-reported quotas. Provider rate-limit responses still fail over; the code does not yet parse Retry-After, implement circuit breakers for AI, or support parallel committee execution. Keep limits below your actual plan allowance. External inference is disabled unless explicitly opted in.
