# Implementation backlog

## M0 foundation
- [x] Docker Compose, TimescaleDB and Redis
- [x] Spring Boot health and instrument-search skeleton
- [x] Python FastAPI health and prototype trap endpoint
- [x] Initial relational schema
- [ ] CI and automated integration tests

## M1 instruments and sources
- [ ] Obtain authorized provider credentials and confirm data licensing
- [ ] Import NSE/BSE instrument masters
- [ ] Normalize ISIN issuer mapping and exchange listings
- [ ] Add exchange calendar and corporate actions
- [ ] Add source registry, source-health UI and ingestion run history
- [ ] Idempotent imports and source revision handling

## M2 market data
- [ ] One authorized provider adapter
- [ ] WebSocket reconnect/heartbeat
- [ ] 1m candle builder, 5m/15m rollups
- [ ] Historical backfill and gap repair
- [ ] Stale-data hard gate

## M3 behaviour and institutions
- [ ] Technical/momentum features, breadth and sector strength
- [ ] FII/DII cash-flow reports
- [ ] Bulk/block/short-sale disclosures
- [ ] Trap engine with labelled historical examples
- [ ] Depth/absorption after licensed depth feed is available

## M4 global intelligence
- [ ] Licensed news provider selection
- [ ] GDELT discovery adapter
- [ ] Official macro sources: RBI, IMF, World Bank and central banks
- [ ] Official filings such as SEC EDGAR for US issuers
- [ ] Entity resolution, event taxonomy, credibility and deduplication

## M5 prediction and risk
- [ ] Point-in-time feature store
- [ ] XGBoost/LightGBM baselines
- [ ] Probability calibration and walk-forward evaluation
- [ ] Cost-aware backtester
- [ ] Very-strict qualification gates

## M6 dashboard and paper research
- [ ] Live read models and WebSocket updates
- [ ] Alerts and signal lifecycle
- [ ] Immutable prediction ledger
- [ ] Paper-trading observation period
- [ ] Model approval and rollback
