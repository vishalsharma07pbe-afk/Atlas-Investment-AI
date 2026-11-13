"""Side-by-side research comparison of independently supplied mutual-fund NAV histories."""
from pydantic import BaseModel,Field,model_validator
from .mutual_fund_history import NavHistoryImport,import_nav_history

class FundComparisonRequest(BaseModel):
    funds:list[NavHistoryImport]=Field(min_length=2,max_length=5)
    @model_validator(mode="after")
    def unique_schemes(self):
        codes=[fund.scheme_code for fund in self.funds]
        if len(set(codes))!=len(codes):raise ValueError("Duplicate scheme codes")
        return self

def compare_funds(request:FundComparisonRequest)->dict:
    results=[import_nav_history(fund) for fund in request.funds]
    latest_dates=[fund["latest_nav"]["as_of"] for fund in results]
    comparable=len(set(latest_dates))==1
    return {
        "funds":[{"scheme_code":fund["scheme_code"],"scheme_name":fund["scheme_name"],
                  "source":fund["source"],"latest_nav":fund["latest_nav"],
                  "trailing_returns_pct":fund["trailing_returns_pct"],
                  "nav_count":fund["nav_count"]} for fund in results],
        "same_latest_nav_date":comparable,
        "comparison_status":"SAME_AS_OF_DATE" if comparable else "DIFFERENT_AS_OF_DATES",
        "return_comparability":"Historical returns use each fund's own NAV dates; do not treat different as-of dates as directly comparable.",
        "rankings":None,"benchmarks":None,"ratings":None,
        "notice":"User-supplied, unverified NAV data. No portfolio weighting, dividends, taxes or fund ratings inferred."
    }
