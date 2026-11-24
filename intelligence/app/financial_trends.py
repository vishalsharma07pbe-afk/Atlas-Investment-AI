"""Conservative annual statement comparisons from cached provider evidence."""
from math import isfinite
import re

METRICS = {
    "REVENUE": ("income_statement", {"revenue", "total revenue", "revenue from operations", "net sales"}),
    "NET_PROFIT": ("income_statement", {"net profit", "net income", "profit after tax", "net profit after tax"}),
    "OPERATING_CASH_FLOW": ("cash_flow", {"cash flow from operating activities", "net cash from operating activities", "net cash flow from operating activities", "operating cash flow"}),
    "TOTAL_ASSETS": ("balance_sheet", {"total_asset"}),
    "TOTAL_LIABILITIES": ("balance_sheet", {"total_liability"}),
}
NOTICE = ("Consolidated yearly provider summaries, not independently reconciled with filings. "
          "Changes describe reported history, not forecasts, valuation or investment advice.")

def _year(value):
    if not isinstance(value, str):
        return None
    # Do not infer years from quarter labels, date ranges or ambiguous FY abbreviations.
    match = re.fullmatch(r"(?:FY\s*)?(20\d{2})", value.strip(), re.I)
    return int(match[1]) if match else None

def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)

def _series(rows, latest_year):
    if not isinstance(rows, list) or not 2 <= len(rows) <= 5:
        return None
    points = {}
    for point in rows:
        if not isinstance(point, dict):
            return None
        year, value = _year(point.get("period")), point.get("value")
        if year is None or year > latest_year or year in points or not _number(value):
            return None
        points[year] = float(value)
    years = sorted(points)
    if years[-1] - years[-2] != 1:
        return None
    return [(year, points[year]) for year in years]

def summarize(report, latest_year):
    sections = report.get("sections", {})
    items, missing = [], []
    for key, (section, aliases) in METRICS.items():
        block = sections.get(section, {})
        data = block.get("data") or {}
        unit = data.get("units")
        rows = data.get("rows") or []
        points = None
        if block.get("status") == "AVAILABLE" and isinstance(unit, str) and unit.strip():
            if section == "balance_sheet":
                field = next(iter(aliases))
                points = _series([{"period": p.get("period"), "value": p.get(field)} for p in rows], latest_year)
            else:
                matching = [r for r in rows if isinstance(r.get("name"), str)
                            and " ".join(r["name"].lower().replace("_", " ").split()) in aliases]
                if len(matching) == 1:
                    points = _series(matching[0].get("history"), latest_year)
        if not points:
            missing.append(key)
            continue
        (previous_year, previous), (year, value) = points[-2:]
        change = value - previous
        if not isfinite(change):
            missing.append(key)
            continue
        # Percentage growth is misleading for zero/negative bases or sign flips.
        percent = 100 * (change / previous) if previous > 0 and value >= 0 else None
        if percent is not None and not isfinite(percent):
            percent = None
        direction = "INCREASED" if change > 0 else "DECREASED" if change < 0 else "UNCHANGED"
        items.append({"metric": key, "section": section, "unit": unit, "previous_year": previous_year,
                      "latest_year": year, "previous_value": previous, "latest_value": value,
                      "change": round(change, 6), "change_percent": round(percent, 4) if percent is not None else None,
                      "direction": direction, "source": block.get("source"),
                      "latest_period_may_be_stale": latest_year - year > 1})
    return {"status": "PARTIAL" if items and missing else "AVAILABLE" if items else "UNAVAILABLE",
            "items": items, "missing_metrics": missing, "notice": NOTICE}
