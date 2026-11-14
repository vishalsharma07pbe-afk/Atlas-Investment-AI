# Authorized Upstox daily OHLCV import

This opt-in adapter calls the Upstox historical v3 daily-candle endpoint and persists observations in the existing provider-aware OHLCV store. It is deliberately **manual CLI only**; no unauthenticated fetch endpoint or unattended scheduler is enabled.

Set `UPSTOX_ACCESS_TOKEN`, `ATLAS_UPSTOX_SYMBOL_MAP` (exact mapping such as `{"RELIANCE":"NSE_EQ|INE002A01018"}`), `ATLAS_UPSTOX_HISTORICAL_AUTHORIZED=true`, `MARKET_DATA_USAGE_RIGHTS_CONFIRMED=true` and `MARKET_DATA_ENTITLEMENT_CONFIRMED=true` only after independently checking the actual provider permissions, plan limits, and terms.

From the `intelligence` directory:

```bash
python -m scripts.import_upstox_history --symbol RELIANCE --market NSE --from-date 2026-11-01 --to-date 2026-11-12
```

The import enforces exact market/instrument mapping, a maximum one-year requested range, provider schema validation, timezone-aware timestamps, source provenance, duplicate protection and rejection of out-of-range candles. It does not adjust for corporate actions, infer exchange trading sessions, or prove live entitlement. Provider response schema and authorized real-account integration remain to be verified. No order placement.
