# ATLAS — ChatGPT plan connection (local preview)

Official local application OAuth. No OpenAI API key, Codex credential reuse, browser cookies or scraping. The plan provider is separately named CHATGPT_PLAN; existing API provider OPENAI remains distinct. No paid API fallback if ATLAS_PAID_AI_ALLOWED=false. Subscription use is subject to account eligibility and shared plan limits.

## Connect after CI and local deployment

1. In ChatGPT Settings → Usage, manage ATLAS app access and disable use of additional paid credits where available. Do not enable if you cannot ensure included usage only. ATLAS cannot inspect or enforce ChatGPT's account-side billing settings. It never purchases credits.
2. In the local .env, update existing keys (do not duplicate them):
```dotenv
ATLAS_CHATGPT_PLAN_ENABLED=true
ATLAS_CHATGPT_PLAN_INCLUDED_ONLY_CONFIRMED=true
ATLAS_AI_PROVIDER_ORDER=CHATGPT_PLAN,OLLAMA
ATLAS_EXTERNAL_AI_ALLOWED=true
ATLAS_AUTOMATIC_AI_REVIEW_ENABLED=true
ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED=true
ATLAS_PAID_AI_ALLOWED=false
ATLAS_CHATGPT_PLAN_RPM=1
ATLAS_CHATGPT_PLAN_RPD=8
```
3. Rebuild/recreate intelligence using your existing protected deployment process. The Compose mapping binds the OAuth callback to host loopback only (127.0.0.1:1455). Ensure the port is unused.
4. Run `docker compose exec intelligence python -m app.chatgpt_plan connect`. Open the printed authorization link in your own browser, approve plan usage, and select an available model in the terminal. Never paste credentials or the authorization link into chat.
5. Check `docker compose exec intelligence python -m app.chatgpt_plan status`. READY_TO_CALL is a configuration state, not inference proof. Observe actual provider health and the investment analyst committee results. Model/API preview eligibility is not guaranteed.
6. Disconnect with `docker compose exec intelligence python -m app.chatgpt_plan disconnect`. Also disconnect ATLAS in ChatGPT Settings if remote revocation is not confirmed. Tokens are in the dedicated local volume, not the research database or ordinary backup.

Public evidence only. Automatic committee reviews prioritize ChatGPT when enabled; existing local validation remains authoritative. Streaming must complete successfully. Usage-limit responses set a five-hour cooldown. Local caps are illustrative and not equivalent to remaining ChatGPT allowance. No paid API fallback is enabled by the documented configuration. Hosted web search capability and live subscription inference still need acceptance; the reasoning adapter does not itself execute a web search.

Official docs: https://developers.openai.com/siwc/token-sharing-open-source
