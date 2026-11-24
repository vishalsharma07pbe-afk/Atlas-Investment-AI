# Automatic horizon research

The existing scheduled market snapshot now computes independent technical watch lists during the same validated daily scan. The manual screener retains its original contract. No extra provider or external AI requests are made. The automated path uses IST dates, excludes current-session bars and applies a four-calendar-day freshness threshold.

Swing uses 50 sessions, positive 20-day momentum, aligned averages, relative volume, RSI, ATR and a historical traded-value proxy. Short-term uses 100 sessions and 60-session momentum. Long-term uses 200 sessions and 120-session momentum. The existing six-month discovery backfill may not yet provide 200 sessions; no long-term watch is published unless adequate stored history exists. Intraday is explicitly blocked until current-session data and liquidity checks exist. These are transparent heuristic technical watch lists, not fully qualified investment recommendations. Fundamental/valuation/event and strategy validation gates remain outstanding. No confidence probabilities or unsupported targets are generated.

The four existing navigation tabs now read cached results, rank up to five watch observations across available exchange samples, display evidence, risks and actual candle dates, and retain the previous manual tools behind an optional disclosure. A failed/stale snapshot cannot supply current candidates. Coverage remains at most 60 instruments per exchange; a historical turnover proxy does not prove live liquidity. No changes to holdings, authentication, credentials, or databases.

Verification: Python rules and UI regression tests cover minimum history, stale data, historical turnover and intraday exclusion; authorized real-data evaluation and strategy calibration are still required.
