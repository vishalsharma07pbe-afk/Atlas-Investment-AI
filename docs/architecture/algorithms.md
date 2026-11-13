# Algorithms and safeguards

## Very-strict signal lifecycle
1. Data gate: valid session, complete candle, healthy provider heartbeat, no unresolved correction.
2. Liquidity gate: minimum 20-day median traded value, spread ceiling, circuit/price-band checks, depth sufficiency only where licensed depth exists.
3. Regime: index returns, breadth, realized volatility and India VIX where available.
4. Setup: opening-range break, VWAP reclaim, pullback or range rejection.
5. Confirmation: relative volume, sector/index relative strength, multi-timeframe alignment and candle close.
6. Participant context: FII/DII aggregate flows and stock-specific disclosed deals remain separate data types with age/scope.
7. Trap/liquidity: failed breakout/breakdown, wick rejection, close back inside range, VWAP reversal, volume-price divergence; order-flow metrics only with trade/depth data.
8. Prediction: calibrated probability for a defined outcome/horizon.
9. Risk: structure stop, ATR sanity bound, targets, estimated slippage and all applicable costs; reject if conservative expected net value is not positive.
10. Publish immutable evidence snapshot, model version, data watermarks, gates, trigger, invalidation and expiry.

## Trap logic
Bull-trap candidate: price breaks precomputed resistance, then a completed candle closes back below it or loses it within a defined confirmation window. Wick rejection, negative price progress per volume, VWAP loss and sector underperformance strengthen the score.
Bear-trap logic is symmetric after a support breakdown and reclaim.
Require reversal confirmation. A trap score is a warning score, not probability. OHLCV cannot prove stop hunting or manipulation.

## Liquidity
With trade-level/depth data: calculate signed volume delta only if aggressor side is supported, depth imbalance, replenishment, spread, cancellations and price impact. High aggressive volume with limited price progress may indicate absorption. Without depth/trade data, mark metrics unavailable, not zero.

## Institutional flows
Keep FII/FPI and DII aggregate reports separate by report date and provisional/final status. Compute rolling 5/20-day net flows and z-scores; compare with index return, breadth and volatility. Bulk/block disclosures are separate stock-specific events. Derivatives client-category positioning is not cash-equity stock-level buying. Retail behaviour remains a proxy unless directly reported.

## Scoring and validation
Score ranks candidates; it is not win probability. Probability is calibrated separately. Use walk-forward validation, point-in-time data, survivorship-aware universes, corporate-action adjustments, realistic fills, costs and an immutable ledger of every signal including untriggered and expired signals.
