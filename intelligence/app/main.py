"""ATLAS intelligence API: research-only evidence framework (Milestone 2 alpha).

This module deliberately does not issue investment recommendations. Factor scores are
user-/upstream-supplied observations, not independently verified market research.
"""
from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal

from fastapi import FastAPI
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
        ],
        "planned": [
            "licensed-provider-activation", "intraday-features",
            "fundamental-research", "institutional-flows", "news-entity-resolution",
            "calibrated-prediction", "backtesting", "portfolio-action-plans",
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
