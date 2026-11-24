# Automatic AI evidence review

The existing autonomous scheduler now selects one not-yet-reviewed technical evidence pack per pass and requests independent grounded commentary from at most two permitted configured models. Existing provider enablement, external/paid consent and SQLite request quotas still apply. Compose enables automatic review by default, but automatic external AI requests require the additional ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED=true opt-in. Without it only configured local Ollama can run. No provider is enabled or given a budget automatically.

Only typed public stock observations, exchange, symbol, date, horizon and explicit missing domains enter prompts. No holdings, portfolio balances, user notes, credentials or private identifiers enter this pipeline. Model findings must cite OBS or LIMITS; invalid findings and trade-action language are rejected. Citation validation is not factual validation. No output changes candidate rankings, evidence gates, targets or recommendation status.

Reviews are keyed to exact evidence and persisted in the existing research SQLite volume. Successful reviews are reused; partial or failed attempts cool down six hours; old records are pruned after 14 days on completion. Review results are suppressed when the associated snapshot is stale or failed, evidence changes or the provider is disabled. The horizon cards show each model separately, never a manufactured agreement probability.

This is a bounded initial autonomous AI review of technical watch candidates, not complete fundamental or portfolio research. Portfolio-specific AI review, fund evidence enrichment, broader scan coverage and independent live provider validation remain outstanding. No trade execution or paid provider activation is introduced.
