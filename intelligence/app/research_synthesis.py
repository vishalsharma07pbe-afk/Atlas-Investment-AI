"""Decision-facing evidence synthesis. No network, private input or generated figures."""
from datetime import date,datetime,timedelta
from math import isfinite

def obj(v):return v if isinstance(v,dict) else {}
def num(v,lo,hi):return type(v) in (int,float) and isfinite(v) and lo<=v<=hi

def current_baseline(b,isin,instant):
    if instant is None or b.get("methodology")!="QUARTER-PERSISTENCE-1" or b.get("qualified") is not False or b.get("isin")!=isin:return False
    try:
        stamp=datetime.fromisoformat(b["capture_at"])
        observed=date.fromisoformat(b["observed_quarter"]);target=date.fromisoformat(b["target_quarter"])
        from zoneinfo import ZoneInfo
        today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
        return (stamp.tzinfo is not None and instant-timedelta(hours=24)<=stamp<=instant
            and observed<today<target and 89<=(target-observed).days<=92 and bool(quarter_scenarios(b)))
    except (ValueError,TypeError,KeyError):return False

def quarter_scenarios(b):
    """Three growth sensitivities around the frozen persistence baseline."""
    metrics=obj(b.get("metrics"));parsed={}
    for k in ("revenue","net_profit"):
        m=obj(metrics.get(k));prior=m.get("target_prior_year_amount_cr");growth=m.get("persisted_growth_percent")
        if not num(prior,.000001,1e12) or not num(growth,-50,100):return []
        parsed[k]=(prior,growth)
    result=[]
    for case,delta in (("BEAR",-10),("BASE",0),("BULL",10)):
        r={"case":case,"growth_shift_pp":delta}
        for k,(prior,growth) in parsed.items():
            r[k+"_growth_percent"]=growth+delta
            r[k+"_amount_cr"]=round(prior*(1+(growth+delta)/100),4)
        r["net_margin_percent"]=round(100*r["net_profit_amount_cr"]/r["revenue_amount_cr"],4) if r["revenue_amount_cr"]>0 else None
        result.append(r)
    return result

def cash_context(value):
    v=obj(value)
    if v.get("methodology")!="VALUATION-SENSITIVITY-1" or v.get("status")!="HYPOTHETICAL_CASH_STREAM_ONLY" or v.get("qualified") is not False:return None
    cases=v.get("scenarios")
    if not isinstance(cases,list) or len(cases)!=3 or [obj(x).get("case") for x in cases]!=["STRESS","ILLUSTRATIVE","OPTIMISTIC"]:return None
    if any(not num(obj(x).get("hypothetical_cash_stream_pv_cr"),.000001,1e15) for x in cases):return None
    return {"status":v["status"],"scenarios":[{k:x[k] for k in ("case","hypothetical_cash_stream_pv_cr")} for x in cases],
        "notice":"Hypothetical discounted cash stream in crore; not enterprise value, equity fair value or share target."}

def fund_context(shortlist,detail,today):
    result={}
    for k,lo,hi in (("weekly_drawdown_percent",-100,0),("worst_rolling_year_percent",-100,1e6),("annualized_volatility_percent",0,1e6),("rolling_peer_above_median_percent",0,100)):
        if num(shortlist.get(k),lo,hi):result[k]=shortlist[k]
    if detail.get("identifier")!=shortlist.get("identifier") or detail.get("plan")!="DIRECT" or detail.get("option")!="GROWTH":return result
    ter=obj(detail.get("automatic_amfi_ter_evidence"));local=obj(detail.get("local_export_evidence"))
    if ter.get("status")=="CONFLICTING_SAME_DATE_TER" or obj(local.get("ter_components_evidence")).get("status")=="CONFLICTING_SAME_DATE_TER":
        result["ter_status"]="CONFLICTING_SAME_DATE_TER";return result
    disclosure=obj(local.get("disclosure"));candidates=[]
    for item,basis,days in ((ter,"AMFI_WEBSITE_OPERATOR_CROSSWALK",7),(disclosure,"OPERATOR_OFFICIAL_EXPORT",90)):
        if basis.startswith("AMFI") and item.get("status")!="OPERATOR_CROSSWALK_MATCH":continue
        isin=shortlist.get("isin_growth")
        if not isinstance(isin,str) or len(isin)!=12 or not isin.startswith("INF") or item.get("isin_growth")!=isin or not num(item.get("ter_percent"),0,100):continue
        try:
            day=date.fromisoformat(item["ter_date"])
            if 0<=(today-day).days<=days:candidates.append((day,basis,item["ter_percent"]))
        except (ValueError,TypeError,KeyError):continue
    if candidates:
        latest=max(x[0] for x in candidates);same=[x for x in candidates if x[0]==latest]
        if max(x[2] for x in same)-min(x[2] for x in same)>.0002:result["ter_status"]="CONFLICTING_SAME_DATE_TER"
        else:
            day,basis,fee=same[0]
            result.update(ter_percent=fee,ter_date=day.isoformat(),ter_basis=basis,ter_status="REPORTED_NOT_INDEPENDENTLY_AUTHENTICATED")
    return result

def thesis(row,is_fund):
    support=[v for v in row.get("reasons",[]) if isinstance(v,str)][:4]
    gaps=[v for v in row.get("limitations",[]) if isinstance(v,str)][:4]
    cautions=[]
    g=obj(row.get("growth_outlook"));facts=obj(row.get("observed_facts"))
    if num(g.get("profit_yoy_percent"),-50,100) and g["profit_yoy_percent"]<=0:cautions.append("Reported-growth persistence assumption is non-positive; verify sustainability.")
    if num(facts.get("reported_pe"),0,1e6) and num(facts.get("reported_sector_pe"),0,1e6) and facts["reported_pe"]>facts["reported_sector_pe"]:cautions.append("Reported P/E exceeds the reported sector multiple; valuation needs verification.")
    if row.get("risk")=="HIGH" or row.get("relative_risk")=="ABOVE_PEER_MEDIAN_DOWNSIDE":cautions.append("Observed historical risk warrants caution.")
    if row.get("tier")=="DRIVER_REVIEW":cautions.append("Underlying business evidence requires review before a new SIP.")
    if not cautions:cautions.append("No additional adverse observation in this bounded evidence set; this is not proof of low risk.")
    return {"status":"CONDITIONAL_EVIDENCE_THESIS","bull_case":support,"bear_case":cautions,
        "base_case":"Compare within the same fund category; confirm horizon, official costs and underlying exposure." if is_fund else "Verify current business, valuation and risk evidence before allocating; no price forecast.",
        "invalidation":["Reassess when new material evidence contradicts the thesis or the underlying evidence becomes stale."],
        "missing_evidence":gaps,"qualified":False}
