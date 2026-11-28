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
    recovery=obj(shortlist.get("recovery_context"))
    if recovery.get("basis")=="MATCHED_WEEKLY_NAV_ANCHORS" and recovery.get("qualified") is False and recovery.get("last_date")==shortlist.get("nav_date"):
        n=recovery.get("completed_recoveries");longest=recovery.get("longest_completed_recovery_days");current=recovery.get("current_underwater_days");draw=recovery.get("current_drawdown_percent")
        if type(n) is int and 0<=n<=156 and (longest is None and n==0 or type(longest) is int and n>0 and 0<longest<=1095) and type(current) is int and 0<=current<=1095 and num(draw,-100,0):
            result["recovery_context"]={k:recovery[k] for k in ("basis","last_date","completed_recoveries","longest_completed_recovery_days","current_underwater_days","current_drawdown_percent","qualified")}
    if detail.get("identifier")!=shortlist.get("identifier") or detail.get("plan")!="DIRECT" or detail.get("option")!="GROWTH":return result
    ter=obj(detail.get("automatic_amfi_ter_evidence"));local=obj(detail.get("local_export_evidence"))
    secondary=obj(detail.get("secondary_disclosure"))
    try:
        disclosed=date.fromisoformat(secondary["document_date"])
        if secondary.get("status")=="SECONDARY_REPORTED_NOT_INDEPENDENTLY_VERIFIED" and 0<=(today-disclosed).days<=90:
            meta={k:secondary[k] for k in ("fund_managers","exit_load") if isinstance(secondary.get(k),str) and 0<len(secondary[k])<=2000}
            if meta:result["reported_metadata"]={**meta,"document_date":disclosed.isoformat(),"basis":"SECONDARY_REPORTED"}
    except (ValueError,TypeError,KeyError):pass
    comparison=obj(local.get("benchmark_comparison"))
    windows=comparison.get("windows")
    if comparison.get("status") in ("MATCHED_LOCAL_TRI_EXPORT","MATCHED_AUTHORIZED_DIRECT_TRI_CSV") and comparison.get("matched_anchors")==157 and comparison.get("rolling_windows")==105 and isinstance(windows,list):
        matched=[w for w in windows if isinstance(w,dict) and w.get("weeks")==156 and w.get("last_date")==shortlist.get("nav_date") and all(num(w.get(k),-100,1e6) for k in ("fund_cagr_percent","tri_cagr_percent","difference_pp"))]
        if len(matched)==1 and num(comparison.get("above_tri_percent"),0,100) and num(comparison.get("annualized_weekly_active_volatility_percent"),0,1e6):
            result["benchmark_context"]={"basis":comparison["status"],"benchmark":obj(local.get("disclosure")).get("benchmark"),"three_year_difference_pp":matched[0]["difference_pp"],"rolling_outperformance_percent":comparison["above_tri_percent"],"active_volatility_percent":comparison["annualized_weekly_active_volatility_percent"],"notice":"Matched historical TRI dates; historical mandate and future outperformance are not established."}
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
    if obj(row.get("fund_evidence")).get("ter_status")=="CONFLICTING_SAME_DATE_TER":cautions.append("Conflicting fund expense evidence; do not use it for a new allocation.")
    if row.get("tier")=="DRIVER_REVIEW":cautions.append("Underlying business evidence requires review before a new SIP.")
    if not cautions:cautions.append("No additional adverse observation in this bounded evidence set; this is not proof of low risk.")
    return {"status":"CONDITIONAL_EVIDENCE_THESIS","bull_case":support,"bear_case":cautions,
        "base_case":"Compare within the same fund category; confirm horizon, official costs and underlying exposure." if is_fund else "Verify current business, valuation and risk evidence before allocating; no price forecast.",
        "invalidation":["Reassess when new material evidence contradicts the thesis or the underlying evidence becomes stale."],
        "missing_evidence":gaps,"qualified":False}


def compact_fund_context(shortlist,reports,category,today):
    """Build bounded public evidence from the full scheduled fund report.

    Do not persist full research reports, source URLs, raw holdings or
    provider messages. Exact code/category/date and unique Direct Growth
    report identity are required.
    """
    result=[]
    for row in shortlist[:5]:
        if not isinstance(row,dict) or row.get("qualified") is not False or row.get("status")!="HISTORICAL_RESEARCH_ONLY":continue
        code,nav,isin=(row.get(k) for k in ("identifier","nav_date","isin_growth"))
        import re
        if not isinstance(code,str) or not re.fullmatch(r"[1-9][0-9]{5,8}",code) or not isinstance(isin,str) or not re.fullmatch(r"INF[A-Z0-9]{9}",isin):continue
        try:
            if not 0<=(today-date.fromisoformat(nav)).days<=7:continue
        except (ValueError,TypeError):continue
        matched=[r for r in reports if isinstance(r,dict) and r.get("identifier")==code]
        if len(matched)!=1:continue
        d=matched[0]
        if d.get("category")!=category or d.get("nav_date")!=nav or d.get("plan")!="DIRECT" or d.get("option")!="GROWTH":continue
        context=fund_context(row,d,today)
        if context.get("ter_status")=="CONFLICTING_SAME_DATE_TER":
            ter=obj(d.get("automatic_amfi_ter_evidence"))
            local=obj(obj(d.get("local_export_evidence")).get("ter_components_evidence"))
            dates=[]
            for source in (ter,local):
                if source.get("status")=="CONFLICTING_SAME_DATE_TER":
                    try:
                        day=date.fromisoformat(source["ter_date"])
                        if 0<=(today-day).days<=7:dates.append(day)
                    except (ValueError,TypeError,KeyError):continue
            # A directly detected cross-source conflict also gets its actual
            # observed date, never the snapshot generation date.
            if not dates:
                for source in (ter,obj(obj(d.get("local_export_evidence")).get("disclosure"))):
                    try:
                        day=date.fromisoformat(source["ter_date"])
                        if 0<=(today-day).days<=7:dates.append(day)
                    except (ValueError,TypeError,KeyError):continue
            if dates:context["ter_conflict_date"]=max(dates).isoformat()
        result.append({"identifier":code,"isin_growth":isin,"nav_date":nav,"category":category,"context":context})
    return result

def saved_fund_context(shortlist,records,category,today,*,website,local,tri,secondary):
    """Revalidate stored projection at read time; revoked consent wins."""
    result=fund_context(shortlist,{},today)
    matches=[r for r in records if isinstance(r,dict) and r.get("identifier")==shortlist.get("identifier")]
    if len(matches)!=1:return result
    record=matches[0]
    if record.get("category")!=category or record.get("isin_growth")!=shortlist.get("isin_growth") or record.get("nav_date")!=shortlist.get("nav_date"):return result
    try:
        if not 0<=(today-date.fromisoformat(record["nav_date"])).days<=7:return result
    except (ValueError,TypeError,KeyError):return result
    c=obj(record.get("context"))
    def fresh(key,days):
        try:return 0<=(today-date.fromisoformat(c[key])).days<=days
        except (KeyError,ValueError,TypeError):return False
    basis=c.get("ter_basis")
    if c.get("ter_status")=="CONFLICTING_SAME_DATE_TER" and (website or local) and fresh("ter_conflict_date",7):
        result.update(ter_status="CONFLICTING_SAME_DATE_TER",ter_conflict_date=c["ter_conflict_date"])
    elif c.get("ter_status")=="REPORTED_NOT_INDEPENDENTLY_AUTHENTICATED" and num(c.get("ter_percent"),0,100):
        if (basis=="AMFI_WEBSITE_OPERATOR_CROSSWALK" and website and fresh("ter_date",7)) or (basis=="OPERATOR_OFFICIAL_EXPORT" and local and fresh("ter_date",90)):
            result.update({k:c[k] for k in ("ter_status","ter_basis","ter_date","ter_percent")})
    b=obj(c.get("benchmark_context"))
    if (local or tri) and b.get("basis") in ("MATCHED_LOCAL_TRI_EXPORT","MATCHED_AUTHORIZED_DIRECT_TRI_CSV") and all(num(b.get(k),lo,hi) for k,lo,hi in (("three_year_difference_pp",-1e6,1e6),("rolling_outperformance_percent",0,100),("active_volatility_percent",0,1e6))):
        result["benchmark_context"]={**{k:b[k] for k in ("basis","three_year_difference_pp","rolling_outperformance_percent","active_volatility_percent")},"benchmark":b.get("benchmark") if isinstance(b.get("benchmark"),str) and len(b["benchmark"])<=150 else None,"notice":"Matched historical TRI dates; historical mandate and future outperformance are not established."}
    m=obj(c.get("reported_metadata"))
    if secondary and m.get("basis")=="SECONDARY_REPORTED":
        try:
            if 0<=(today-date.fromisoformat(m["document_date"])).days<=90:
                values={k:m[k] for k in ("fund_managers","exit_load") if isinstance(m.get(k),str) and 0<len(m[k])<=2000}
                if values:result["reported_metadata"]={**values,"basis":m["basis"],"document_date":m["document_date"]}
        except (ValueError,TypeError,KeyError):pass
    return result


def forecast_challengers(baseline):
    """Expose only reconciled original forecast experiments, not fitted estimates."""
    if baseline.get("challenger_policy")!="FIXED_CHALLENGERS_V1":return []
    result=[]
    for model in ("HALF_PERSISTENCE","DAMPED_ACCELERATION"):
        metrics={}
        for metric in ("revenue","net_profit"):
            original=obj(obj(baseline.get("metrics")).get(metric))
            entry=obj(obj(obj(baseline.get("challengers")).get(metric)).get(model))
            g=entry.get("growth_percent");a=entry.get("amount_cr");base=original.get("target_prior_year_amount_cr")
            if not num(g,-50,100) or not num(a,0,1e12) or not num(base,.000001,1e12) or abs(a-round(base*(1+g/100),6))>max(.00001,base*1e-8):continue
            metrics[metric]={"growth_percent":g,"amount_cr":a}
        if len(metrics)==2:result.append({"model":model,"metrics":metrics,"qualified":False})
    return result

def filing_context(row,instant):
    """Exact issuer/provider quarter reconciliation already acquired by the NSE worker."""
    from . import nse_financial_filings
    from zoneinfo import ZoneInfo
    if instant is None or not nse_financial_filings.permitted():return None
    f=obj(row.get("independent_financial_evidence"));c=obj(f.get("comparison"));p=obj(c.get("profit_comparison"))
    if f.get("status")!="REPORTED_CONSOLIDATED_FILING" or f.get("isin")!=row.get("isin") or f.get("scope")!="CONSOLIDATED":return None
    try:
        stamp=datetime.fromisoformat(f["retrieved_at"]);period=date.fromisoformat(f["period"])
        today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
        if stamp.tzinfo is None or not instant-timedelta(hours=24)<=stamp<=instant or not nse_financial_filings.fresh_period(period,today):return None
    except (ValueError,TypeError,KeyError):return None
    import re
    if not isinstance(f.get("source_sha256"),str) or not re.fullmatch(r"[a-f0-9]{64}",f["source_sha256"]):return None
    revenue=c.get("status");profit=p.get("status")
    if revenue not in ("WITHIN_ILLUSTRATIVE_TOLERANCE","REVENUE_DIFFERENCE_REVIEW","NOT_COMPARABLE") or profit not in ("BOTH_BASES_WITHIN_TOLERANCE","ONE_REPORTED_BASIS_WITHIN_TOLERANCE","PROFIT_DIFFERENCE_REVIEW","NOT_COMPARABLE",None):return None
    status="CONFLICT_REVIEW" if revenue=="REVENUE_DIFFERENCE_REVIEW" or profit=="PROFIT_DIFFERENCE_REVIEW" else "CORROBORATED_REPORTED_QUARTER" if revenue=="WITHIN_ILLUSTRATIVE_TOLERANCE" and profit in ("BOTH_BASES_WITHIN_TOLERANCE","ONE_REPORTED_BASIS_WITHIN_TOLERANCE") else "PARTIAL_COMPARISON"
    return {"status":status,"period":f["period"],"retrieved_at":stamp.isoformat(),"source_sha256":f["source_sha256"],
        "revenue_comparison":revenue,"profit_comparison":profit,"automatic_index_source":f.get("acquisition_method")==nse_financial_filings.INDEX_METHOD,
        "qualified":False,"notice":"Issuer/provider arithmetic corroboration under illustrative tolerances; net profit accounting basis may differ. Not audit certification."}
