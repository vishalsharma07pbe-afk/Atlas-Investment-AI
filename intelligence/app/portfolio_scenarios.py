"""Deterministic portfolio stress scenarios, never forecasts.

Only holdings with explicitly recorded prices participate in the scenario.
Unpriced holdings remain visible as missing coverage rather than being assigned
fabricated values.
"""
from decimal import Decimal, ROUND_HALF_UP

SCENARIOS = (
    ("SEVERE_DOWNSIDE", Decimal("-0.30")),
    ("BEAR", Decimal("-0.15")),
    ("BASE_UNCHANGED", Decimal("0")),
    ("BULL", Decimal("0.15")),
)

def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def stress_portfolio(holdings):
    invested = Decimal("0")
    valued_invested = Decimal("0")
    valued = Decimal("0")
    unpriced = []
    breakdown = []
    for h in holdings:
        cost = h.quantity * h.average_cost
        invested += cost
        if h.last_price is None:
            unpriced.append({"id": h.id, "symbol": h.symbol, "asset_type": h.asset_type})
            continue
        market_value = h.quantity * h.last_price
        valued += market_value
        valued_invested += cost
        breakdown.append({
            "id": h.id, "symbol": h.symbol, "asset_type": h.asset_type,
            "recorded_value": money(market_value),
            "weight_percent": None,
        })
    for item in breakdown:
        item["weight_percent"] = (
            money(Decimal(item["recorded_value"]) * 100 / valued) if valued else None
        )
    scenarios = []
    for label, shock in SCENARIOS:
        stressed = valued * (1 + shock)
        scenarios.append({
            "name": label,
            "assumed_uniform_price_change_percent": money(shock * 100),
            "stressed_value_of_priced_holdings": money(stressed),
            "change_from_recorded_value": money(stressed - valued),
            "unrealized_pnl_vs_priced_cost": money(stressed - valued_invested),
        })
    return {
        "status": "COMPLETE_PRICED_SUBSET" if not unpriced else "PARTIAL_PRICE_COVERAGE",
        "price_source": "MANUALLY_RECORDED_NOT_LIVE",
        "total_invested_all_holdings": money(invested),
        "priced_holdings_cost": money(valued_invested),
        "recorded_value_priced_holdings": money(valued),
        "unpriced_holdings": unpriced,
        "priced_holdings": breakdown,
        "scenarios": scenarios,
        "method": "UNIFORM_INDEPENDENT_PRICE_SHOCK_ON_PRICED_HOLDINGS_ONLY",
        "notice": "Illustrative arithmetic, not a forecast, probability, investment advice, or correlated risk model.",
    }
