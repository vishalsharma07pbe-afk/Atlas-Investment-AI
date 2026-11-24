"""ATLAS intelligence API: research-only evidence framework (Milestone 2 alpha).

This module deliberately does not issue investment recommendations. Factor scores are
user-/upstream-supplied observations, not independently verified market research.
"""
from datetime import date, datetime, timezone
import sqlite3
from enum import Enum
from typing import Literal

from fastapi import FastAPI,HTTPException,Request as FastAPIRequest
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from .config import settings
from .market_client import backend_json
from .technical import Candle, compute, levels
from .patterns import detect
from .institutional_flows import FlowRequest
from .news_events import NewsRequest
from .research_alerts import AlertRequest

app = FastAPI(
    title="ATLAS Trading Intelligence Engine",
    version="0.2.0",
    description="Research-only evidence and risk assessment. No order execution.",
)


class TrapInput(BaseModel):
    direction: Literal["UPSIDE_BREAKOUT", "DOWNSIDE_BREAKDOWN"]
    broke_level: bool
    reversal_confirmed: bool
    relative_volume: float = Field(ge=0)
    wick_ratio: float = Field(ge=0, le=1)
    vwap_conflict: bool
    close_back_inside_range: bool


class ResearchDomain(str, Enum):
    FUNDAMENTALS = "FUNDAMENTALS"
    FINANCIAL_STATEMENTS = "FINANCIAL_STATEMENTS"
    VALUATION = "VALUATION"
    TECHNICALS = "TECHNICALS"
    PRICE_VOLUME = "PRICE_VOLUME"
    INSTITUTIONAL_FLOWS = "INSTITUTIONAL_FLOWS"
    SENTIMENT = "SENTIMENT"
    TRAP_DETECTION = "TRAP_DETECTION"
    MACRO = "MACRO"
    NEWS_EVENTS = "NEWS_EVENTS"
    SECTOR_PEERS = "SECTOR_PEERS"
    GOVERNANCE = "GOVERNANCE"
    LIQUIDITY = "LIQUIDITY"
    PORTFOLIO_FIT = "PORTFOLIO_FIT"
    MODEL_VALIDATION = "MODEL_VALIDATION"
    SCENARIOS = "SCENARIOS"


class EvidenceItem(BaseModel):
    domain: ResearchDomain
    factor: str = Field(min_length=3, max_length=200)
    source: str = Field(min_length=3, max_length=500)
    observed_at: datetime
    finding: str = Field(min_length=3, max_length=2000)
    risk_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
    quality: Literal["VERIFIED", "UNVERIFIED", "MISSING"]
    # Optional qualitative research only; no uncalibrated numeric probability.
    supports_thesis: Literal["SUPPORTS", "CONTRADICTS", "NEUTRAL", "UNKNOWN"]

    @model_validator(mode="after")
    def check_timestamp(self):
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include a timezone offset")
        if self.observed_at > datetime.now(timezone.utc):
            raise ValueError("observed_at cannot be in the future")
        return self


class ResearchRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9._&-]+$")
    asset_type: Literal["EQUITY", "MUTUAL_FUND"]
    context: Literal["CURRENT_HOLDING", "NEW_OPPORTUNITY"]
    horizon: Literal["INTRADAY", "SWING", "SHORT_TERM", "LONG_TERM"]
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=500)


@app.get("/health")
def health():
    return {
        "status": "UP", "service": "intelligence", "mode": "RESEARCH_ONLY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/intelligence/capabilities")
def capabilities():
    return {
        "implemented": [
            "health", "capability-discovery", "prototype-trap-rule",
            "evidence-intake", "research-coverage", "preliminary-risk-triage",
            "recommendation-blocking", "daily-technical-indicators",
            "explainable-pattern-detection", "technical-research-summary",
            "authorized-company-fundamentals", "sector-relative-key-ratios",
            "financial-statement-summaries", "shareholding-history",
            "corporate-actions", "sector-competitors", "cited-company-news",
            "aggregate-fii-dii-cash-activity", "portfolio-concentration-review",
            "mutual-fund-evidence-gated-ranking", "on-demand-research-alerts",
            "grounded-natural-language-research", "source-cited-ai-explanations",
            "walk-forward-signal-evaluation", "leakage-controlled-backtesting",
            "calibration-and-model-monitoring", "multi-factor-screening",
            "risk-profiled-goal-scenarios", "inflation-and-tax-drag-planning",
        ],
        "planned": [
            "licensed-provider-activation", "intraday-features",
            "official-mutual-fund-category-and-portfolio-disclosures",
            "bulk-block-deal-source", "transaction-ledger-xirr",
            "persistent-alert-rules-and-delivery", "news-entity-resolution",
            "persisted-user-screeners-and-watchlists", "regulated-tax-lot-optimization",
            "portfolio-action-plans",
        ],
        "live_data_connected": False,
        "provider_mode": settings.provider,
        "actionable_recommendations_enabled": False,
    }

@app.get("/api/v1/intelligence/providers/status")
def provider_status():
    """Truthful provider readiness; never expose credentials or claim live access."""
    from .provider_readiness import ProviderConfig,provider_readiness
    return provider_readiness(ProviderConfig(
        provider=settings.provider,
        access_token=settings.upstox_token,
        automatic_refresh=settings.automatic_refresh,
        licensed_data_access=settings.licensed_data_access,
        entitlement_confirmed=settings.entitlement_confirmed,
        rate_per_second=settings.request_rate_per_second,
    ))


# P1: authorized fundamentals, cited news, and aggregate institutional evidence.
@app.get("/api/v1/intelligence/p1/companies/{isin}")
def p1_company_research(isin: str, instrument_key: str | None = None):
    from .p1_research import company_research
    try:
        return company_research(isin, instrument_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from .multi_provider_quotes import ProviderFailure
        if isinstance(exc, ProviderFailure):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise


@app.get("/api/v1/intelligence/p1/news")
def p1_company_news(instrument_keys: str, page_size: int = 20):
    from .p1_research import company_news
    try:
        return company_news(instrument_keys.split(","), page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from .multi_provider_quotes import ProviderFailure
        if isinstance(exc, ProviderFailure):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise


@app.get("/api/v1/intelligence/p1/institutional-activity")
def p1_institutional_activity(interval: str = "1D"):
    from .p1_research import institutional_activity
    try:
        return institutional_activity(interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def _technical_payload(instrument_id:int,limit:int=1000):
    raw=backend_json(f"/api/v1/market-data/instruments/{instrument_id}/candles?limit={max(1,min(limit,2000))}")
    candles=[Candle(str(x["trade_date"]),float(x["open"]),float(x["high"]),float(x["low"]),float(x["close"]),int(x["volume"]),x["adjustment_status"],int(x["revision"])) for x in raw["candles"]]
    if not candles:return raw,candles,{},[]
    indicators=compute(candles);patterns=detect(candles,indicators)
    return raw,candles,indicators,patterns

@app.get("/api/v1/intelligence/technical/{instrument_id}")
def technical_analysis(instrument_id:int,limit:int=1000):
    raw,candles,indicators,patterns=_technical_payload(instrument_id,limit)
    if not candles:return {"instrument":raw["instrument"],"timeframe":"1d","status":"UNAVAILABLE_NO_VALIDATED_CANDLES","candles":[],"indicators":{},"patterns":[],"missing_data":["VALIDATED_DAILY_CANDLES"]}
    mixed=len({x.adjustment_status for x in candles})>1
    series={name:[{"time":candles[i].date,"value":round(value,6)} for i,value in enumerate(values) if value is not None] for name,values in indicators.items()}
    latest={name:(round(values[-1],6) if values and values[-1] is not None else None) for name,values in indicators.items()}
    return {"instrument":raw["instrument"],"timeframe":"1d","status":"READY" if len(candles)>=20 else "INSUFFICIENT_HISTORY",
            "as_of":candles[-1].date,"candle_count":len(candles),"adjustment_statuses":sorted({x.adjustment_status for x in candles}),
            "candles":raw["candles"],"indicators":series,"latest_indicators":latest,"levels":levels(candles),
            "patterns":[{"instrument":raw["instrument"],"timeframe":"1d",**p} for p in patterns],
            "missing_data":(["MIXED_ADJUSTMENT_STATUS"] if mixed else [])+(["TRUE_INTRADAY_VWAP_UNAVAILABLE_FROM_DAILY_CANDLES"]),
            "calculation_version":"M2-DAILY-1","notice":"Observations only; no forecast, target price, BUY or SELL recommendation."}

@app.get("/api/v1/intelligence/technical/{instrument_id}/summary")
def technical_summary(instrument_id:int,limit:int=1000):
    data=technical_analysis(instrument_id,limit)
    if data["status"].startswith("UNAVAILABLE"):return {**data,"research":None}
    li=data["latest_indicators"];close=float(data["candles"][-1]["close"]);bull=[];bear=[];risks=[]
    sma50=li.get("sma_50");sma200=li.get("sma_200");rsi14=li.get("rsi_14");macd=li.get("macd");signal=li.get("macd_signal")
    trend="INSUFFICIENT_HISTORY"
    if sma50 is not None: trend="UPTREND" if close>sma50 else "DOWNTREND"
    if sma200 is not None and sma50 is not None: trend="UPTREND" if close>sma50>sma200 else "DOWNTREND" if close<sma50<sma200 else "MIXED"
    if sma50 is not None:(bull if close>sma50 else bear).append("Close is above SMA 50." if close>sma50 else "Close is below SMA 50.")
    if macd is not None and signal is not None:(bull if macd>signal else bear).append("MACD is above its signal line." if macd>signal else "MACD is below its signal line.")
    if rsi14 is not None and rsi14>70:risks.append("RSI 14 is above 70; this is an observation, not a reversal forecast.")
    if rsi14 is not None and rsi14<30:risks.append("RSI 14 is below 30; this is an observation, not a rebound forecast.")
    return {"instrument":data["instrument"],"timeframe":"1d","as_of":data["as_of"],"status":data["status"],"research":{"trend":trend,
      "momentum":"POSITIVE" if (li.get("momentum_20d") or 0)>0 else "NEGATIVE" if li.get("momentum_20d") is not None else "INSUFFICIENT_HISTORY",
      "volatility_annualized":li.get("historical_volatility_20"),"relative_volume":li.get("relative_volume_20"),"support_resistance":data["levels"],
      "patterns":data["patterns"][-10:],"bullish_evidence":bull,"bearish_evidence":bear,"risk_observations":risks,
      "missing_data":data["missing_data"],"source_freshness":{"latest_verified_date":data["as_of"],"is_live":False}},
      "notice":"Rule-based technical observations, not a forecast or investment recommendation."}


@app.post("/api/v1/intelligence/traps/evaluate")
def evaluate_trap(data: TrapInput):
    evidence = {
        "break_detected": data.broke_level,
        "reversal_confirmed": data.reversal_confirmed,
        "relative_volume_elevated": data.relative_volume >= 1.8,
        "wick_rejection": data.wick_ratio >= 0.55,
        "vwap_conflict": data.vwap_conflict,
        "failed_close": data.close_back_inside_range,
    }
    score = sum(bool(v) for v in evidence.values())
    detected = data.broke_level and data.reversal_confirmed and score >= 4
    return {
        "detected": detected,
        "trap_type": (
            "BULL_TRAP" if data.direction == "UPSIDE_BREAKOUT" else "BEAR_TRAP"
        ) if detected else None,
        "prototype_score": score,
        "evidence": evidence,
        "warning": "Prototype heuristic only; not proof of manipulation or institutional intent.",
    }


@app.post("/api/v1/intelligence/research/evaluate")
def evaluate_research(data: ResearchRequest):
    """Assess submitted evidence completeness; NEVER return a trade action.

    Coverage is a domain-presence metric, not a measure of research correctness.
    Risk tier is a preliminary severity triage, not a quantitative risk model.
    """
    required = set(ResearchDomain)
    verified_domains = {
        item.domain for item in data.evidence if item.quality == "VERIFIED"
    }
    covered = sorted(domain.value for domain in verified_domains)
    missing = sorted(domain.value for domain in required - verified_domains)
    critical = [
        {"domain": item.domain.value, "factor": item.factor, "finding": item.finding}
        for item in data.evidence
        if item.risk_severity == "CRITICAL"
    ]
    high = [
        {"domain": item.domain.value, "factor": item.factor, "finding": item.finding}
        for item in data.evidence
        if item.risk_severity == "HIGH"
    ]
    unverified = sum(item.quality != "VERIFIED" for item in data.evidence)
    if critical or high:
        preliminary_risk = "HIGH"
    elif any(item.risk_severity == "MEDIUM" for item in data.evidence):
        preliminary_risk = "MEDIUM"
    elif missing or unverified or not data.evidence or any(
        item.risk_severity == "UNKNOWN" for item in data.evidence
    ):
        preliminary_risk = "UNKNOWN"
    else:
        preliminary_risk = "LOW"

    blockers = ["NO_CONNECTED_VERIFIED_MARKET_FEED", "NO_VALIDATED_RECOMMENDATION_MODEL"]
    if missing:
        blockers.append("REQUIRED_RESEARCH_DOMAINS_INCOMPLETE")
    if unverified:
        blockers.append("UNVERIFIED_OR_MISSING_EVIDENCE")
    if critical:
        blockers.append("CRITICAL_RISK_FLAGS")

    return {
        "symbol": data.symbol.upper(),
        "asset_type": data.asset_type,
        "context": data.context,
        "horizon": data.horizon,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "research": {
            "domains_total": len(required),
            "domains_with_verified_evidence": len(verified_domains),
            "coverage_percent": round(100 * len(verified_domains) / len(required), 1),
            "covered_domains": covered,
            "missing_domains": missing,
            "evidence_items": len(data.evidence),
            "unverified_or_missing_items": unverified,
        },
        "risk": {
            "preliminary_category": preliminary_risk,
            "method": "SEVERITY_TRIAGE_NOT_CALIBRATED_RISK_SCORE",
            "critical_flags": critical,
            "high_flags": high,
        },
        "decision": {
            "status": "RESEARCH_INCOMPLETE",
            "suggested_action": "NO_ACTION",
            "actionable": False,
            "blockers": blockers,
        },
        "disclaimer": (
            "Research intake only. Submitted evidence is not independently verified by "
            "ATLAS. Coverage is not a confidence score. No investment advice or "
            "trade execution is provided."
        ),
    }

# Milestone 3: read-only portfolio research aggregation.
# The backend URL is fixed to the internal Docker service; never accept arbitrary URLs.
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import HTTPException, Query
from pydantic import ValidationError

_BACKEND_HOLDINGS_URL = settings.backend_url.rstrip("/") + "/api/v1/portfolio/holdings"


class PortfolioHolding(BaseModel):
    id: int
    symbol: str = Field(min_length=1, max_length=50)
    asset_type: Literal["EQUITY", "MUTUAL_FUND"]
    quantity: Decimal = Field(ge=0)
    average_cost: Decimal = Field(ge=0)
    last_price: Decimal | None = Field(default=None, ge=0)
    price_as_of: datetime | None = None


def _fetch_portfolio_holdings() -> list[PortfolioHolding]:
    request = Request(_BACKEND_HOLDINGS_URL, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise HTTPException(status_code=502, detail="Portfolio backend returned an unexpected status")
            # Limit data read to 2 MB to avoid uncontrolled memory consumption.
            payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                raise HTTPException(status_code=502, detail="Portfolio response exceeds size limit")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Portfolio backend unavailable") from exc

    try:
        import json
        records = json.loads(payload)
        if not isinstance(records, list):
            raise ValueError("Expected a list")
        return [PortfolioHolding.model_validate(item) for item in records]
    except (ValueError, TypeError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail="Portfolio backend returned invalid holdings data") from exc


@app.get("/api/v1/intelligence/portfolio/research")
def portfolio_research(
    horizon: Literal["INTRADAY", "SWING", "SHORT_TERM", "LONG_TERM"] = Query(default="LONG_TERM"),
):
    """Aggregate saved holdings and research-readiness checks; no trade signals."""
    holdings = _fetch_portfolio_holdings()
    total_invested = Decimal("0")
    total_valued = Decimal("0")
    valued_positions = []
    assessments = []
    for holding in holdings:
        invested = holding.quantity * holding.average_cost
        total_invested += invested
        market_value = holding.quantity * holding.last_price if holding.last_price is not None else None
        if market_value is not None:
            total_valued += market_value
            valued_positions.append((holding.id, market_value))

        research_request = ResearchRequest(
            symbol=holding.symbol,
            asset_type=holding.asset_type,
            context="CURRENT_HOLDING",
            horizon=horizon,
        )
        research_result = evaluate_research(research_request)
        assessments.append({
            "holding_id": holding.id,
            "symbol": holding.symbol,
            "asset_type": holding.asset_type,
            "quantity": str(holding.quantity),
            "average_cost": str(holding.average_cost),
            "last_price": str(holding.last_price) if holding.last_price is not None else None,
            "price_as_of": holding.price_as_of.isoformat() if holding.price_as_of else None,
            "invested": str(invested),
            "market_value": str(market_value) if market_value is not None else None,
            "unrealized_pnl": str(market_value - invested) if market_value is not None else None,
            "portfolio_weight_percent": None,
            "research": research_result,
        })

    # Weights are calculated only after all holdings have been processed.
    for assessment in assessments:
        market_value = assessment["market_value"]
        assessment["portfolio_weight_percent"] = (
            round(float(100 * Decimal(market_value) / total_valued), 2)
            if market_value is not None and total_valued > 0 else None
        )

    warnings = []
    if len(holdings) < 5 and holdings:
        warnings.append("CONCENTRATION_WATCH_FEWER_THAN_FIVE_HOLDINGS")
    if len(valued_positions) != len(holdings):
        warnings.append("SOME_HOLDINGS_HAVE_NO_MANUALLY_RECORDED_PRICE")
    for assessment in assessments:
        weight = assessment["portfolio_weight_percent"]
        if weight is not None and weight > 25:
            warnings.append(f"HOLDING_EXCEEDS_25_PERCENT:{assessment['symbol']}:{assessment['holding_id']}")

    return {
        "status": "RESEARCH_INCOMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "LOCAL_PORTFOLIO_BACKEND",
        "price_source": "MANUALLY_ENTERED_NOT_LIVE",
        "horizon": horizon,
        "portfolio": {
            "holdings_count": len(holdings),
            "holdings_with_recorded_prices": len(valued_positions),
            "total_invested": str(total_invested),
            "total_recorded_market_value": str(total_valued),
            "concentration_warnings": warnings,
        },
        "holdings": assessments,
        "actionable_recommendations_enabled": False,
        "notice": "Read-only portfolio research readiness. No independent market evidence, calibrated risk tier, investment recommendation, or trade execution.",
    }


@app.get("/api/v1/intelligence/portfolio/stress-scenarios")
def portfolio_stress_scenarios():
    """Illustrative, uniform portfolio shocks; excludes unpriced holdings."""
    from .portfolio_scenarios import stress_portfolio
    return stress_portfolio(_fetch_portfolio_holdings())


@app.get("/api/v1/intelligence/screener/daily")
def daily_screener(exchange: Literal["NSE", "BSE"] | None = None, limit: int = Query(default=20, ge=1, le=20), max_age_days: int = Query(default=7, ge=0, le=30)):
    """On-demand daily sample only; no background work or market-wide claim."""
    from urllib.parse import urlencode
    from .screener import screen
    params = {"limit": limit}
    if exchange:
        params["exchange"] = exchange
    instruments = backend_json("/api/v1/instruments?" + urlencode(params))
    if not isinstance(instruments, list):
        raise HTTPException(status_code=502, detail="Invalid instrument registry response")
    def load(instrument_id):
        return backend_json(f"/api/v1/market-data/instruments/{instrument_id}/candles?limit=250")
    return screen(instruments, load, max_age_days=max_age_days)


@app.post("/api/v1/intelligence/institutional-flows/analyze")
def institutional_flow_analysis(request: "FlowRequest"):
    """Compute net flows from user-provided, source-attributed records only."""
    from .institutional_flows import analyze_flows
    try:
        return analyze_flows(request.records)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/intelligence/news/analyze")
def news_evidence_analysis(request: NewsRequest):
    """Classify freshness of source-attributed user-supplied news events."""
    from .news_events import analyze_news
    try:
        return analyze_news(request.events,request.max_age_hours)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@app.get("/api/v1/intelligence/backtest/{instrument_id}")
def daily_backtest(instrument_id: int, fast: int = Query(default=10,ge=2,le=199), slow: int = Query(default=30,ge=3,le=200), fee_bps: int = Query(default=10,ge=0,le=100), slippage_bps: int = Query(default=5,ge=0,le=100)):
    """Run a bounded historical simulation from stored validated daily candles."""
    from .backtesting import backtest
    if fast >= slow:
        raise HTTPException(status_code=422,detail="Fast SMA must be smaller than slow SMA")
    raw=backend_json(f"/api/v1/market-data/instruments/{instrument_id}/candles?limit=1000")
    try:
        return backtest(raw,fast=fast,slow=slow,fee_bps=fee_bps,slippage_bps=slippage_bps)
    except (ValueError,KeyError,TypeError,OverflowError) as exc:
        raise HTTPException(status_code=422,detail="Backtest input failed OHLCV validation") from exc


@app.get("/api/v1/intelligence/risk-qualification/{instrument_id}")
def risk_qualification(instrument_id: int, max_age_days: int = Query(default=7,ge=0,le=30)):
    """Read-only historical research gate, not a trading signal."""
    from .risk_qualification import qualify
    raw=backend_json(f"/api/v1/market-data/instruments/{instrument_id}/candles?limit=250")
    return qualify(raw,max_age_days=max_age_days)


@app.post("/api/v1/intelligence/research-alerts/evaluate")
def evaluate_research_alerts(request: AlertRequest):
    """Evaluate daily threshold alerts on demand; no scheduling or push delivery."""
    from .research_alerts import evaluate_alerts
    raw=backend_json(f"/api/v1/market-data/instruments/{request.instrument_id}/candles?limit=250")
    return evaluate_alerts(raw,request.rules,max_age_days=request.max_age_days)


@app.get("/api/v1/intelligence/providers/upstox/daily-preview")
def upstox_daily_preview(instrument_key: str = Query(min_length=8,max_length=40),
                         from_date: date = Query(),to_date: date = Query()):
    """Opt-in, read-only provider historical candle preview; never ingests data."""
    from .upstox_preview import preview_daily
    return preview_daily(instrument_key,from_date,to_date)


@app.get("/api/v1/intelligence/market/overview")
def integrated_market_overview(exchange: Literal["NSE","BSE"] | None = None,
                               limit: int = Query(default=20,ge=1,le=20),
                               max_age_days: int = Query(default=7,ge=0,le=30)):
    """Daily sampled breadth, momentum, volume and anomaly observations."""
    from urllib.parse import urlencode
    from .market_intelligence import analyze_market
    params={"limit":limit}
    if exchange:params["exchange"]=exchange
    instruments=backend_json("/api/v1/instruments?"+urlencode(params))
    if not isinstance(instruments,list):
        raise HTTPException(status_code=502,detail="Invalid instrument registry response")
    def load(instrument_id):
        return backend_json(f"/api/v1/market-data/instruments/{instrument_id}/candles?limit=250")
    return analyze_market(instruments,load,max_age_days=max_age_days)


from .provider_batch import BatchRequest,review_batch

@app.post("/api/v1/intelligence/providers/upstox/batch-review")
def upstox_batch_review(request:BatchRequest):
    """Bounded, on-demand provider health review. Never persists candles."""
    return review_batch(request)


from .provider_reconciliation import ReconciliationRequest,reconcile

@app.post("/api/v1/intelligence/providers/reconcile")
def provider_reconciliation(request:ReconciliationRequest):
    """Review explicit instrument mapping and session/adjustment evidence; no writes."""
    return reconcile(request)


from .broker_reports import ReportRequest,report

@app.post("/api/v1/intelligence/reports/brokers/consolidated")
def consolidated_broker_report(request:ReportRequest):
    """User-supplied cross-broker position aggregation; no broker connections."""
    return report(request)


from .broker_research import ConsensusRequest,consensus,SOURCES

@app.get("/api/v1/intelligence/research/brokers/sources")
def broker_research_sources():
    return {"sources":SOURCES,"automatic_collection_enabled":False,"notice":"User-submitted research comparison only."}

@app.post("/api/v1/intelligence/research/brokers/compare")
def compare_broker_research(request:ConsensusRequest):
    return consensus(request)


from .research_ingestion import IngestionReview,audit_manifests

@app.post("/api/v1/intelligence/research/brokers/ingestion-review")
def broker_research_ingestion_review(request:IngestionReview):
    """Audit source declarations before any future permitted collection."""
    return audit_manifests(request)


from .research_coverage import CoverageRequest,coverage

@app.post("/api/v1/intelligence/research/brokers/coverage")
def broker_research_coverage(request:CoverageRequest):
    """Per-provider user-submitted report coverage, without invented feeds."""
    return coverage(request)


from .research_outcomes import OutcomeRequest,evaluate

@app.post("/api/v1/intelligence/research/brokers/outcomes")
def broker_research_outcomes(request:OutcomeRequest):
    """Review historical research against dated prices without lookahead."""
    return evaluate(request)


from fastapi import HTTPException
from .notifications import summary as notification_summary,details as notification_details

@app.get("/api/v1/intelligence/notifications/summary")
def notifications_summary():
    """Lightweight IDs for badge; never returns notification details."""
    try:return notification_summary()
    except RuntimeError:raise HTTPException(status_code=503,detail="Local notification source unavailable")

@app.get("/api/v1/intelligence/notifications")
def notifications_details():
    """Fetch full notification details only when explicitly requested."""
    try:return notification_details()
    except RuntimeError:raise HTTPException(status_code=503,detail="Local notification source unavailable")


from .notification_source_health import inspect_sources

@app.get("/api/v1/intelligence/notifications/sources/health")
def notification_source_health():
    """Read-only diagnostics for locally configured IPO notification sources."""
    try:return inspect_sources()
    except (ValueError,OSError):raise HTTPException(status_code=503,detail="Notification source health unavailable")

from .ipo_operations import import_history

@app.get("/api/v1/intelligence/notifications/providers/import-history")
def ipo_provider_import_history():
    """Read only bounded, sanitized local import history; never initiates provider fetch."""
    try:return import_history()
    except (ValueError,OSError,TypeError):raise HTTPException(status_code=503,detail="IPO import history unavailable")

from .portfolio_allocation import PlanRequest,allocation_plan

@app.post("/api/v1/intelligence/portfolio/allocation-plan")
def portfolio_allocation_plan(request:PlanRequest):
    """On-demand, read-only contribution planner using locally recorded holdings."""
    return allocation_plan(_fetch_portfolio_holdings(),request)

from .goal_planning import GoalRequest,goal_projection

@app.post("/api/v1/intelligence/planning/goal-projection")
def planning_goal_projection(request:GoalRequest):
    """Pure illustrative calculations, without price feeds or persisted personal goals."""
    return goal_projection(request)

from .goal_comparison import ComparisonRequest,compare_scenarios

@app.post('/api/v1/intelligence/planning/goal-comparison')
def planning_goal_comparison(request:ComparisonRequest):
    return compare_scenarios(request)

from fastapi import HTTPException
from .research_journal import JournalEntryInput,list_entries,create_entry,update_entry,delete_entry

@app.get("/api/v1/intelligence/journal")
def journal_list():
    try:return {"entries":list_entries()}
    except (ValueError,OSError) as exc:raise HTTPException(status_code=503,detail="Local journal unavailable") from exc

@app.post("/api/v1/intelligence/journal",status_code=201)
def journal_create(entry:JournalEntryInput):
    try:return create_entry(entry)
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc
    except OSError as exc:raise HTTPException(status_code=503,detail="Local journal unavailable") from exc

@app.put("/api/v1/intelligence/journal/{entry_id}")
def journal_update(entry_id:str,entry:JournalEntryInput):
    try:result=update_entry(entry_id,entry)
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc
    except OSError as exc:raise HTTPException(status_code=503,detail="Local journal unavailable") from exc
    if result is None:raise HTTPException(status_code=404,detail="Journal entry not found")
    return result

@app.delete("/api/v1/intelligence/journal/{entry_id}",status_code=204)
def journal_delete(entry_id:str):
    try:found=delete_entry(entry_id)
    except (ValueError,OSError) as exc:raise HTTPException(status_code=503,detail="Local journal unavailable") from exc
    if not found:raise HTTPException(status_code=404,detail="Journal entry not found")

from .fee_impact import FeeRequest,fee_impact

@app.post("/api/v1/intelligence/planning/fee-impact")
def planning_fee_impact(request:FeeRequest):
    return fee_impact(request)

from .portfolio_concentration import LimitsRequest,concentration_report

@app.post("/api/v1/intelligence/portfolio/concentration")
def portfolio_concentration(request:LimitsRequest):
    """Read-only concentration report for locally recorded holdings."""
    return concentration_report(_fetch_portfolio_holdings(),request)

from .market_readiness import ReadinessPolicy,evaluate_readiness

@app.get("/api/v1/intelligence/market/readiness")
def market_data_readiness(
    max_calendar_age_days: int = Query(default=7,ge=0,le=30),
    minimum_instruments: int = Query(default=1,ge=1,le=1000000),
    minimum_candles: int = Query(default=1,ge=1,le=100000000),
    require_live_feed: bool = True,
):
    """Fail-closed evaluation of locally recorded source health, no provider calls."""
    health=backend_json("/api/v1/data-health/summary")
    if not isinstance(health,dict):
        raise HTTPException(status_code=502,detail="Invalid backend data-health response")
    from .data_readiness import live_feed_observation
    from datetime import datetime, timezone
    health = {**health, "liveMarketDataConnected": live_feed_observation(datetime.now(timezone.utc))}
    return evaluate_readiness(health,ReadinessPolicy(
        max_calendar_age_days=max_calendar_age_days,
        minimum_instruments=minimum_instruments,
        minimum_candles=minimum_candles,
        require_live_feed=require_live_feed,
    ))

from .upstox_authorization import authorization_diagnostics

@app.get("/api/v1/intelligence/providers/upstox/feed-authorization-readiness")
def upstox_feed_authorization_readiness():
    """Safe configuration-only diagnostics; never returns credentials or signed feed URLs."""
    from .config import settings
    return authorization_diagnostics(
        settings.provider,
        bool(settings.upstox_token and settings.upstox_token.strip()),
        settings.licensed_data_access,
        settings.entitlement_confirmed,
    )

from .instrument_resolution import resolve_upstox_instrument

@app.get("/api/v1/intelligence/providers/upstox/resolve")
def resolve_stock_for_upstox(instrument_id: int):
    """Read-only local registry resolution, not a market-data subscription."""
    from fastapi import HTTPException
    if instrument_id <= 0:
        raise HTTPException(status_code=422,detail="Invalid instrument ID")
    record=backend_json(f"/api/v1/instruments/{instrument_id}")
    return resolve_upstox_instrument(record)

from .upstox_quote_worker import quote_worker

@app.get("/api/v1/intelligence/providers/upstox/quote-status")
def upstox_quote_status():
    """Read-only worker status; never reveal credentials or unverified quotes."""
    gate=authorization_diagnostics(settings.provider,bool(settings.upstox_token),
                                   settings.licensed_data_access,settings.entitlement_confirmed)
    from .dynamic_feed_selection import dynamic_feed_selection
    return {**feed_supervisor.status(),
            "automatic_selection":dynamic_feed_selection.last_status,
            "worker_running":quote_worker.running,
            "transport_connected":quote_worker.cache.connected,
            "configuration_status":gate["status"],
            "blockers":gate["blockers"],
            **quote_worker.cache.diagnostics()}

from .upstox_live_quote import current_quote

@app.get("/api/v1/intelligence/providers/upstox/quote")
def upstox_current_quote(symbol: str, instrument_key: str):
    """Fetch one read-only quote for an instrument selected from the server registry."""
    return current_quote(symbol, instrument_key)

from .market_indices import snapshots as market_index_snapshots

@app.get("/api/v1/intelligence/market/indices")
def market_indices():
    """Fetch a bounded set of Indian index snapshots in one authorized request."""
    return market_index_snapshots()

@app.get("/api/v1/intelligence/providers/upstox/quotes/{instrument_id}")
def upstox_instrument_quote(instrument_id:int):
    from fastapi import HTTPException
    if instrument_id<=0:raise HTTPException(status_code=422,detail="Invalid instrument ID")
    record=backend_json(f"/api/v1/instruments/{instrument_id}")
    resolution=resolve_upstox_instrument(record)
    if not resolution["subscription_ready"]:
        return {"status":"UNAVAILABLE","quote":None,"reason":resolution["blocker"]}
    if not (settings.provider=="UPSTOX" and settings.licensed_data_access and settings.entitlement_confirmed):
        return {"status":"UNAVAILABLE","quote":None,"reason":"PROVIDER_RIGHTS_NOT_VERIFIED"}
    return quote_worker.cache.snapshot(resolution["instrument_key"])

@app.get("/api/v1/internal/live/market-indices")
async def internal_live_market_indices(request: FastAPIRequest):
    """Internal push stream; Spring authenticates the browser before relaying it."""
    _require_internal_service(request)
    from .live_events import changed_events,index_snapshot
    return StreamingResponse(changed_events(index_snapshot),media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.get("/api/v1/internal/live/instruments/{instrument_id}")
async def internal_live_instrument(instrument_id:int,request:FastAPIRequest):
    _require_internal_service(request)
    if instrument_id<=0:raise HTTPException(status_code=422,detail="Invalid instrument ID")
    record=backend_json(f"/api/v1/instruments/{instrument_id}")
    resolution=resolve_upstox_instrument(record)
    if not resolution["subscription_ready"]:
        raise HTTPException(status_code=422,detail=resolution["blocker"])
    key=resolution["instrument_key"]
    from .live_events import changed_events,instrument_snapshot
    await dynamic_feed_selection.subscribe(key)
    async def events():
        try:
            async for event in changed_events(lambda:instrument_snapshot(key)):
                yield event
        finally:
            await dynamic_feed_selection.unsubscribe(key)
    return StreamingResponse(events(),media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

from .upstox_supervisor import feed_supervisor,startup_feed
from .dynamic_feed_selection import dynamic_feed_selection

@app.on_event("startup")
async def start_opt_in_upstox_feed():
    await startup_feed()
    await dynamic_feed_selection.start()

@app.on_event("shutdown")
async def stop_opt_in_upstox_feed():
    await dynamic_feed_selection.stop()
    await feed_supervisor.stop()

@app.post("/api/v1/intelligence/providers/upstox/subscriptions/reconcile")
async def reconcile_upstox_portfolio_subscriptions():
    """Safe idempotent refresh after a holding changes; never accepts credentials or keys."""
    return await dynamic_feed_selection.reconcile()

from .mutual_fund_nav import FundNavRequest,analyze_nav

@app.post("/api/v1/intelligence/mutual-funds/nav-analysis")
def mutual_fund_nav_analysis(request:FundNavRequest):
    """Calculate read-only NAV performance from explicitly attributed user data."""
    return analyze_nav(request)

from .amfi_nav_import import AmfiImportRequest,parse_amfi

@app.post("/api/v1/intelligence/mutual-funds/amfi-nav-import")
def import_amfi_nav_snapshot(request:AmfiImportRequest):
    """Inspect caller-provided NAV snapshot without storing or verifying it."""
    from fastapi import HTTPException
    try:
        result=parse_amfi(request.text,request.scheme_codes)
    except ValueError:
        raise HTTPException(status_code=422,detail="Invalid NAV snapshot or scheme selection") from None
    result["source"]["name"]=request.source_name
    return result

from .mutual_fund_history import NavHistoryImport,import_nav_history

@app.post("/api/v1/intelligence/mutual-funds/nav-history-import")
def mutual_fund_history_import(request:NavHistoryImport):
    """Validate one exact scheme's source-attributed NAV history and calculate returns."""
    from fastapi import HTTPException
    try:
        return import_nav_history(request)
    except ValueError:
        raise HTTPException(status_code=422,detail="Invalid historical NAV CSV or scheme selection") from None

from .mutual_fund_comparison import FundComparisonRequest,compare_funds

@app.post("/api/v1/intelligence/mutual-funds/compare")
def mutual_fund_compare(request:FundComparisonRequest):
    """Compare source-attributed NAV histories without ranking unverified funds."""
    from fastapi import HTTPException
    try:
        return compare_funds(request)
    except ValueError:
        raise HTTPException(status_code=422,detail="Invalid fund comparison histories") from None

from .mutual_fund_reconciliation import FundReconciliationRequest,reconcile_funds

@app.post("/api/v1/intelligence/mutual-funds/reconcile")
def mutual_fund_reconcile(request:FundReconciliationRequest):
    """Read-only valuation comparison; never mutate recorded portfolio values."""
    return reconcile_funds(request)

from .provider_batch_preflight import BatchPreflightRequest,preflight_batch

@app.post("/api/v1/intelligence/providers/batch-preflight")
def provider_batch_preflight(request:BatchPreflightRequest):
    """Inspect prospective provider records without ingesting or authorizing collection."""
    return preflight_batch(request)

from .nav_refresh_preflight import NavRefreshPreflightRequest,preflight_nav_refresh

@app.post("/api/v1/intelligence/mutual-funds/nav-refresh-preflight")
def mutual_fund_nav_refresh_preflight(request:NavRefreshPreflightRequest):
    """Validate an explicitly supplied NAV refresh batch without storing or fetching."""
    return preflight_nav_refresh(request)

from .mutual_fund_planning import FundPlanningRequest,plan_funds

@app.post("/api/v1/intelligence/mutual-funds/plan")
def mutual_fund_plan(request:FundPlanningRequest):
    """Illustrative SIP and read-only recorded portfolio analytics."""
    return plan_funds(request)

from .mutual_fund_goals import FundGoalRequest,goal_plan

@app.post("/api/v1/intelligence/mutual-funds/goal-plan")
def mutual_fund_goal_plan(request:FundGoalRequest):
    """Read-only monthly SIP target and shortfall analysis."""
    from fastapi import HTTPException
    try:
        return goal_plan(request)
    except ValueError:
        raise HTTPException(status_code=422,detail="Goal is outside supported SIP planning limits") from None

from .mutual_fund_risk import FundRiskRequest,assess_fund_risk

@app.post("/api/v1/intelligence/mutual-funds/portfolio-risk")
def mutual_fund_portfolio_risk(request:FundRiskRequest):
    """Read-only recorded-value concentration; no inferred fund risk scores."""
    return assess_fund_risk(request)

from .mutual_fund_historical_risk import HistoricalRiskRequest,historical_risk

@app.post("/api/v1/intelligence/mutual-funds/historical-risk")
def mutual_fund_historical_risk(request:HistoricalRiskRequest):
    """Read-only historical NAV risk diagnostics."""
    return historical_risk(request)

from .mutual_fund_scheme_search import SchemeSearchRequest,search_schemes
@app.post("/api/v1/intelligence/mutual-funds/scheme-search")
def mutual_fund_scheme_search(request:SchemeSearchRequest):
    """Search names/codes within an explicitly supplied NAV snapshot, read only."""
    return search_schemes(request)

from .mutual_fund_snapshot_pipeline import SnapshotPortfolioRequest,inspect_snapshot_portfolio
@app.post("/api/v1/intelligence/mutual-funds/snapshot-portfolio-review")
def mutual_fund_snapshot_portfolio_review(request:SnapshotPortfolioRequest):
    """Review supplied NAV snapshot against explicitly mapped fund holdings, without writing."""
    return inspect_snapshot_portfolio(request)

# Local NAV catalog plus a documented, public daily Upstox instrument snapshot.
from fastapi import HTTPException, Request as FastAPIRequest
from .nav_catalog import import_snapshot, search_schemes, catalog_status, MAX_BYTES

@app.get("/api/v1/intelligence/mutual-funds/status")
def mutual_fund_catalog_status():
    from .nav_auto_refresh import scheduler
    return {**catalog_status(),"scheduler":scheduler.status()}

@app.post("/api/v1/intelligence/mutual-funds/refresh")
def mutual_fund_catalog_refresh():
    from .nav_auto_refresh import refresh_once
    try:
        return refresh_once()
    except RuntimeError as exc:
        raise HTTPException(status_code=503,detail=str(exc)) from exc

@app.get("/api/v1/intelligence/mutual-funds/search")
def mutual_fund_catalog_search(q: str = "", limit: int = 30):
    try:
        return search_schemes(q, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/v1/intelligence/mutual-funds/details/{fund_identifier}")
def mutual_fund_catalog_details(fund_identifier: str):
    from .nav_catalog import fund_details
    try:
        return fund_details(fund_identifier)
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc)=="FUND_NOT_FOUND" else 400,detail=str(exc)) from exc

@app.get("/api/v1/intelligence/mutual-funds/recommendations")
def mutual_fund_recommendations(category: str = "LARGE_CAP",horizon_months: int = 60,
                                risk_tolerance: str = "MODERATE"):
    from .mutual_fund_recommendations import dashboard
    try:
        return dashboard(category,horizon_months,risk_tolerance)
    except ValueError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc

@app.post("/api/v1/intelligence/mutual-funds/import")
async def mutual_fund_catalog_import(request: FastAPIRequest):
    # Loopback-only service behind the local frontend proxy; no external exposure.
    # Importing data is a local user action, not an authorized automated feed.
    if request.headers.get("content-length") and int(request.headers["content-length"]) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="NAV_FILE_TOO_LARGE")
    payload = await request.body()
    if len(payload) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="NAV_FILE_TOO_LARGE")
    try:
        return import_snapshot(payload.decode("utf-8-sig"))
    except UnicodeError:
        raise HTTPException(status_code=400, detail="NAV_FILE_NOT_UTF8")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

from .flow_ledger import import_evidence, list_evidence

@app.post("/api/v1/intelligence/institutional-flows/ledger")
def institutional_flow_ledger_import(request: FlowRequest):
    try:
        return import_evidence(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@app.get("/api/v1/intelligence/institutional-flows/ledger")
def institutional_flow_ledger_list(limit: int = 100):
    return list_evidence(limit)

from .news_ledger import import_news, list_news

@app.post("/api/v1/intelligence/news/ledger")
def news_ledger_import(request: NewsRequest):
    try:
        return import_news(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@app.get("/api/v1/intelligence/news/ledger")
def news_ledger_list(limit: int = 50, max_age_hours: int = 72, geography: str | None = None):
    try:
        return list_news(limit, max_age_hours, geography)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

from .data_readiness import readiness as get_data_readiness

@app.get("/api/v1/intelligence/data-readiness")
def data_readiness():
    """Read-only source readiness. Never asserts live connectivity from local imports."""
    return get_data_readiness()

# Read-only entitlement declaration review. This never enables collection.
from fastapi import HTTPException as EntitlementHTTPException
from .entitlement_registry import entitlement_preflight, entitlement_summary

@app.get("/api/v1/intelligence/entitlements")
def entitlement_registry_status():
    return entitlement_summary()

@app.get("/api/v1/intelligence/entitlements/preflight")
def entitlement_registry_preflight(dataset: str, mode: str, purpose: str = "PERSONAL_RESEARCH"):
    try:
        return entitlement_preflight(dataset, mode, purpose)
    except ValueError as exc:
        raise EntitlementHTTPException(status_code=400, detail=str(exc)) from exc

from .ingestion_quality import BatchRequest, inspect_batch

@app.post("/api/v1/intelligence/ingestion/quality-preflight")
def ingestion_quality_preflight(request: BatchRequest):
    """Validate a candidate batch without storing data or authorizing a feed."""
    return inspect_batch(request)

# Local readiness incident snapshots. No external feeds or trade side effects.
from .reliability_incidents import record_snapshot as record_reliability_snapshot, history as reliability_history

@app.get("/api/v1/intelligence/reliability/incidents")
def reliability_incidents(limit: int = 50):
    try:
        return reliability_history(limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/intelligence/reliability/observe")
def reliability_observe():
    return monitor_observe_once()

# Optional, local-only scheduled observations. No external market data collection.
from .reliability_monitor import monitor as readiness_monitor, observe_once as monitor_observe_once
app.add_event_handler("startup", readiness_monitor.start)
app.add_event_handler("shutdown", readiness_monitor.stop)

from .nav_auto_refresh import scheduler as nav_refresh_scheduler
app.add_event_handler("startup", nav_refresh_scheduler.start)
app.add_event_handler("shutdown", nav_refresh_scheduler.stop)

@app.get("/api/v1/intelligence/reliability/monitor")
def reliability_monitor_status():
    return readiness_monitor.status()

# Read-only feed observability. Does not start, reconnect, or authorize a provider.
from .feed_health import assess_feed

@app.get("/api/v1/intelligence/providers/upstox/feed-health")
def upstox_feed_health():
    return assess_feed(upstox_quote_status())

@app.get("/api/v1/intelligence/data-hub/sources")
def data_hub_sources():
    from .data_hub import health
    return health()

@app.get("/api/v1/intelligence/data-hub/search")
def data_hub_search(query: str, asset_type: Literal["EQUITY", "MUTUAL_FUND"]):
    from fastapi import HTTPException
    from .data_hub import lookup
    try:
        return lookup(query, asset_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/intelligence/data-hub/failover-readiness")
def failover_readiness():
    from .provider_router import readiness
    return readiness()

@app.get("/api/v1/intelligence/mutual-funds/{scheme_code}/history")
def mutual_fund_scheme_history(scheme_code: int, limit: int = 365):
    from .nav_catalog import scheme_history
    try:
        return scheme_history(scheme_code, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.get("/api/v1/intelligence/mutual-funds/import-audit")
def mutual_fund_import_audit(limit: int = 20):
    from .nav_catalog import import_audit
    try:
        return import_audit(limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.get("/api/v1/intelligence/data-hub/quotes/{symbol}")
def multi_provider_equity_quote(symbol: str, max_age_seconds: int = 60):
    """Read-only, fail-closed quotes. No cached value is misrepresented as current."""
    from .multi_provider_quotes import quote_status
    try:
        return quote_status(symbol, max_age_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.get("/api/v1/intelligence/data-hub/provider-adapters")
def multi_provider_adapter_status():
    from .multi_provider_quotes import provider_status
    return provider_status()

@app.get("/api/v1/intelligence/data-hub/ohlcv/{market}/{symbol}")
def ohlcv_history(market: str, symbol: str, limit: int = 365):
    """Read-only imported daily candles; includes source and age."""
    from .ohlcv_store import history
    try:
        return history(symbol, market, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# P2: grounded research, leakage-controlled evaluation, explainable screening,
# and assumption-driven planning. None of these endpoints execute orders.
from .p2_research import (AdvancedScreenRequest, GroundedResearchRequest,
                          advanced_screen, grounded_answer)
from .p2_planning import PlanningRequest, personalized_plan


@app.post("/api/v1/intelligence/p2/research/answer")
def p2_grounded_research(request: GroundedResearchRequest):
    from .ai_failover import grounded_research
    try:
        return grounded_answer(request, grounded_research if request.use_ai else None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/intelligence/p2/backtest/{instrument_id}")
def p2_walk_forward_backtest(instrument_id: int,
                             lookback: int = Query(default=20, ge=5, le=100),
                             train_size: int = Query(default=120, ge=60, le=1000),
                             test_size: int = Query(default=20, ge=5, le=250),
                             fee_bps: int = Query(default=10, ge=0, le=100)):
    from .p2_backtesting import walk_forward
    raw = backend_json(f"/api/v1/market-data/instruments/{instrument_id}/candles?limit=2000")
    try:
        return walk_forward(raw, lookback=lookback, train_size=train_size,
                            test_size=test_size, fee_bps=fee_bps)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/intelligence/p2/screener/evaluate")
def p2_advanced_screener(request: AdvancedScreenRequest):
    return advanced_screen(request)


@app.post("/api/v1/intelligence/p2/planning")
def p2_personalized_planning(request: PlanningRequest):
    return personalized_plan(request)

# Research-only AI committee endpoints. Internal caller authentication required.
import os
import secrets
from fastapi import Request as FastAPIRequest

def _require_internal_service(request: FastAPIRequest):
    expected=os.getenv("INTERNAL_SERVICE_TOKEN","")
    received=request.headers.get("X-Atlas-Service-Token","")
    if len(expected)<32 or not secrets.compare_digest(expected,received):
        raise HTTPException(status_code=401,detail="INTERNAL_SERVICE_AUTH_REQUIRED")

from .sanitizer import AllowlistedAnalysisPayload
from .consensus import committee
from .ai_failover import provider_health as ai_provider_health

@app.get("/api/v1/ai/providers/health")
def ai_providers_health(request: FastAPIRequest):
    _require_internal_service(request)
    return ai_provider_health()

@app.post("/api/v1/ai/analyze/{symbol}")
async def ai_analyze(symbol: str, observations: AllowlistedAnalysisPayload, request: FastAPIRequest):
    _require_internal_service(request)
    if observations.symbol != symbol:
        raise HTTPException(status_code=422,detail="SYMBOL_MISMATCH")
    return await committee(symbol,observations.model_dump(exclude={"symbol"},exclude_none=True))

# Autonomous research uses the existing validated screen and fund ranking engines.
from .autonomous_research import scheduler as research_scheduler, read_snapshot as research_snapshot
app.add_event_handler("startup", research_scheduler.start)
app.add_event_handler("shutdown", research_scheduler.stop)

@app.get("/api/v1/intelligence/research/overview")
def autonomous_research_overview():
    """Read cached public-market research; no provider calls or user data."""
    try:
        return research_snapshot()
    except (OSError, ValueError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail="Research snapshot storage unavailable") from exc

@app.get("/api/v1/intelligence/research/watch-outcomes")
def automatic_watch_outcomes(horizon: Literal["SWING", "SHORT_TERM", "LONG_TERM"] = "SWING"):
    from .watch_outcomes import summary
    from .autonomous_research import _connect
    try:
        return summary(_connect, horizon)
    except (OSError, ValueError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail="Watch outcome history unavailable") from exc

class PortfolioThesisIdentity(BaseModel):
    isin: str = Field(pattern=r"^IN[A-Z0-9]{10}$")
    exchange: Literal["NSE","BSE"]
    model_config = {"extra":"forbid"}


class PortfolioThesisRead(BaseModel):
    identities: list[PortfolioThesisIdentity] = Field(max_length=100)
    model_config = {"extra":"forbid"}


@app.post("/api/v1/internal/portfolio-thesis")
def internal_portfolio_thesis(request: FastAPIRequest, body: PortfolioThesisRead):
    _require_internal_service(request)
    from .portfolio_thesis import read
    try:
        return read([item.model_dump() for item in body.identities])
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503,detail="Portfolio evidence unavailable") from exc


@app.get("/api/v1/internal/portfolio-opportunities")
def internal_portfolio_opportunities(request: FastAPIRequest):
    """Read a bounded public-only shortlist for the authenticated Spring service."""
    _require_internal_service(request)
    from .portfolio_opportunities import read
    try:
        return read()
    except (ValueError, OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail="Public opportunity evidence unavailable") from exc
