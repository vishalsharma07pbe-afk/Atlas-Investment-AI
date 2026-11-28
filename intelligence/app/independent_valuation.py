"""Opt-in, operator-reviewed source-bound FCFF/FCFE and earnings scenarios.

No inferred capex, share count, discount rate or price. Source documents are
hashed from the protected read-only mount; operator review is not independent
authentication by ATLAS. No network or external AI.
"""
from datetime import date,datetime,timedelta
from pathlib import Path
from hashlib import sha256
from math import isfinite
from zoneinfo import ZoneInfo
import json,os,re,stat
from .replay_evidence import exact_isin

VERSION="SOURCE-BOUND-VALUATION-1"
PATH=Path("/app/filing-reports/valuation-evidence.json")
MAX_BYTES=2_000_000
MAX_DOC=20_000_000
MAX_TOTAL_DOCUMENT_BYTES=100_000_000
def num(v,lo,hi):return type(v) in (int,float) and isfinite(v) and lo<=v<=hi
def permitted():
    return os.getenv("ATLAS_VALUATION_EVIDENCE_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def bounded_read(path,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as f:
        before=os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=limit:raise ValueError("FILE")
        data=f.read(limit+1);after=os.fstat(f.fileno())
        if len(data)!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns or len(data)>limit:raise ValueError("CHANGED_FILE")
        return data

def discounted_equity(cash,g,d,t,debt):
    """Five-year constant growth and Gordon terminal, amounts in crore."""
    flow=sum(cash*(1+g/100)**i/(1+d/100)**i for i in range(1,6))
    terminal=cash*(1+g/100)**5*(1+t/100)/((d-t)/100)/(1+d/100)**5
    return flow+terminal-debt

def implied_growth(cash,shares,price,d,t,debt):
    """Solve only inside the declared scenario model's bounded growth range."""
    target=price*shares
    lo,hi=-40.,40.
    a=discounted_equity(cash,lo,d,t,debt);b=discounted_equity(cash,hi,d,t,debt)
    if not a<=target<=b:
        return {"status":"OUTSIDE_DECLARED_GROWTH_RANGE","growth_percent":None}
    for _ in range(64):
        mid=(lo+hi)/2
        if discounted_equity(cash,mid,d,t,debt)<target:lo=mid
        else:hi=mid
    return {"status":"SOLVED_CONDITIONAL_MARKET_IMPLIED_GROWTH","growth_percent":round((lo+hi)/2,4)}

def scenario(e,today):
    if not exact_isin(e.get("isin")) or e.get("operator_reviewed") is not True or e.get("scope")!="CONSOLIDATED_INR_CRORE":return None
    model=e.get("model");sector=e.get("sector_type")
    if (model,sector) not in (("FCFF","NON_FINANCIAL"),("FCFE","NON_FINANCIAL"),("DIVIDEND_DISCOUNT","FINANCIAL")):return None
    try:
        fiscal=date.fromisoformat(e["fiscal_period_end"]);quote=date.fromisoformat(e["price_date"]);capture=date.fromisoformat(e["review_date"])
        if not 0<=(today-fiscal).days<=550 or not 0<=(today-quote).days<=5 or not fiscal<=capture<=today or (today-capture).days>30:return None
        if e.get("price_basis")!="ACTUAL_UNADJUSTED_INR" or e.get("same_share_basis") is not True:return None
        shares=e["diluted_shares_cr"];price=e["price_inr"];net_debt=e.get("net_debt_cr")
        if not num(shares,.000001,1e7) or not num(price,.01,1e8):return None
        if model=="FCFF" and not num(net_debt,-1e12,1e12):return None
        # Exact signed inputs; never derive free cash from aggregate investing flow.
        if model=="FCFF":
            fields=("ebit_cr","depreciation_cr","capex_cr","working_capital_increase_cr","tax_rate_percent")
            if not all(num(e.get(k),-1e12,1e12) for k in fields) or not num(e["tax_rate_percent"],0,50) or e["capex_cr"]<0 or e["depreciation_cr"]<0:return None
            cash=e["ebit_cr"]*(1-e["tax_rate_percent"]/100)+e["depreciation_cr"]-e["capex_cr"]-e["working_capital_increase_cr"]
        elif model=="FCFE":
            if not all(num(e.get(k),-1e12,1e12) for k in ("operating_cash_cr","capex_cr","net_borrowing_cr")) or e["capex_cr"]<0:return None
            cash=e["operating_cash_cr"]-e["capex_cr"]+e["net_borrowing_cr"]
        else:cash=e.get("annual_dividends_cr")
        if not num(cash,.000001,1e12):return None
        cases=e["scenarios"]
        if not isinstance(cases,list) or [c.get("case") for c in cases]!=["BEAR","BASE","BULL"]:return None
        out=[]
        for c in cases:
            g,d,t=(c.get(k) for k in ("growth_percent","discount_percent","terminal_growth_percent"))
            if not num(g,-40,40) or not num(d,5,40) or not num(t,0,8) or d-t<2:return None
            value=discounted_equity(cash,g,d,t,net_debt if model=="FCFF" else 0)
            per_share=value/shares
            if not num(per_share,-1e8,1e8):return None
            row={"case":c["case"],"growth_percent":g,"discount_percent":d,"terminal_growth_percent":t,
                "equity_value_cr":round(value,4),"conditional_value_per_share":round(per_share,4),
                "upside_downside_percent":round(100*(per_share/price-1),4),
                "margin_of_safety_percent":round(100*(1-price/per_share),4) if per_share>0 else None}
            profit=c.get("next_year_net_profit_cr")
            if num(profit,-1e12,1e12):row["conditional_eps"]=round(profit/shares,4)
            out.append(row)
        if not out[0]["conditional_value_per_share"]<=out[1]["conditional_value_per_share"]<=out[2]["conditional_value_per_share"]:return None
        base=out[1]
        reverse=implied_growth(cash,shares,price,base["discount_percent"],base["terminal_growth_percent"],net_debt if model=="FCFF" else 0)
        reverse.update(discount_percent=base["discount_percent"],terminal_growth_percent=base["terminal_growth_percent"],declared_base_growth_percent=base["growth_percent"],qualified=False,notice="Conditional five-year cash growth implied by the reference quote using the same operator-reviewed base discount and terminal assumptions. Not consensus, expected growth or a price target.")
        return {"reverse_valuation":reverse,"methodology":VERSION,"status":"OPERATOR_SOURCE_BOUND_VALUATION_SCENARIO","isin":e["isin"],"model":model,
            "fiscal_period_end":fiscal.isoformat(),"price_date":quote.isoformat(),"price_inr":price,"review_date":capture.isoformat(),
            "cash_base_cr":round(cash,4),"scenarios":out,"qualified":False,
            "notice":"Operator-reviewed source-bound cash/share inputs and explicit assumptions; not independently audited, calibrated, or an executable price target."}
    except (TypeError,ValueError,KeyError,OverflowError,AttributeError,ZeroDivisionError):return None

def read(instant,path=PATH,*,identities=None):
    if not permitted():return {}
    try:
        today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
        root=json.loads(bounded_read(path,MAX_BYTES))
        if root.get("methodology")!=VERSION or root.get("authorization_attested") is not True:return {}
        rows=root["companies"]
        if not isinstance(rows,list) or len(rows)>200:return {}
        output={};conflict=set();hashes={};total_bytes=0
        for e in rows:
            if not isinstance(e,dict) or identities is not None and e.get("isin") not in identities:continue
            result=scenario(e,today)
            if not result:continue
            sources=e.get("sources")
            if not isinstance(sources,list) or len(sources)!=3 or {x.get("role") for x in sources if isinstance(x,dict)}!={"FINANCIAL_STATEMENTS","SHARE_AND_PRICE_BASIS","VALUATION_ASSUMPTIONS"}:continue
            verified=[]
            for src in sources:
                if not isinstance(src,dict):break
                name=src.get("file");digest=src.get("sha256")
                if not isinstance(name,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,120}",name) or ".." in name or not isinstance(digest,str) or not re.fullmatch(r"[a-f0-9]{64}",digest):break
                if name not in hashes:
                    try:
                        remaining=MAX_TOTAL_DOCUMENT_BYTES-total_bytes
                        if remaining<=0:return {}
                        raw=bounded_read(path.parent/name,min(MAX_DOC,remaining))
                        total_bytes+=len(raw);hashes[name]=sha256(raw).hexdigest()
                    except (OSError,ValueError):hashes[name]=None
                if hashes[name]!=digest:break
                verified.append(digest)
            if len(set(verified))!=3:continue
            result["source_hashes"]=verified
            isin=result["isin"]
            if isin in output and output[isin]!=result:conflict.add(isin)
            output[isin]=result
        return {k:v for k,v in output.items() if k not in conflict}
    except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError):return {}
