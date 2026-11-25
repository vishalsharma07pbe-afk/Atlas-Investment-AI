"""Combine existing global observations; sector questions, never inferred sensitivity."""
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from zoneinfo import ZoneInfo

from . import global_fx, global_macro, global_markets
from .replay_evidence import exact_isin

GROUPS={
    "CURRENCIES":tuple(a+"_"+b for a,b in global_fx.PAIRS),
    "OIL":tuple(global_macro.FIELDS["OIL"]),
    "US_YIELDS":tuple(global_macro.FIELDS["YIELDS"]),
    "EQUITY_INDICES":("SP500","DJIA","NASDAQCOM","NIKKEI225"),
    "PRECIOUS_METALS":("GOLD","SILVER"),
}
TOTAL=sum(len(v) for v in GROUPS.values())
NOTICE=("Separate source-dated observations from existing authorized caches. Five-observation changes are not synchronized global sessions. "
        "Missing evidence is not neutral. No combined risk-on/off score, forecast, correlation or recommendation.")
EXPOSURE_NOTICE=("Exact reported sector label selects generic research questions only. Actual revenue geography, input costs, debt, "
                 "hedging, pricing power and company sensitivity remain unverified. No predicted benefit, loss or ranking change.")
# Exact normalized labels only; never infer from ticker or substring.
QUESTIONS={
    "information technology": {
        "USD_INR":"Check actual export revenue, billing currencies, foreign costs and currency hedges.",
        "NASDAQCOM":"Check overseas client demand and relevant technology spending disclosures."},
    "air transport service":{
        "RBRTE":"Check aviation fuel costs, fuel hedges, fare pass-through and actual procurement benchmarks.",
        "USD_INR":"Check foreign-currency lease, fuel and debt exposure."},
    "oil & gas":{
        "RBRTE":"Check upstream versus downstream revenue, inventory valuation, benchmark exposure and hedges.",
        "RWTC":"Check which crude benchmarks actually enter contracts and margins.",
        "USD_INR":"Check import bills, export revenue and currency hedges."},
    "automobile":{
        "RBRTE":"Check actual fuel-related demand, logistics and material cost exposure.",
        "USD_INR":"Check imported components, export mix and currency hedges."},
    "banks":{
        "US10Y":"Check foreign funding, duration and disclosed interest-rate exposure; US yields are not Indian policy rates.",
        "USD_INR":"Check net foreign-currency assets, liabilities and hedges."},
    "finance":{
        "US10Y":"Check funding mix, refinancing needs and duration sensitivity.",
        "USD_INR":"Check foreign-currency liabilities and hedges."},
    "gems, jewellery & watches":{
        "GOLD":"Check gold inventory, hedging and customer price pass-through.",
        "SILVER":"Check actual silver input or inventory exposure.",
        "USD_INR":"Check metal import costs and currency hedges."},
    "pharmaceuticals":{
        "USD_INR":"Check overseas sales, imported inputs, billing currencies and hedges.",
        "SP500":"Check actual overseas demand and company-specific regulatory evidence."},
}
ALIASES={"it - software":"information technology","it - services":"information technology",
         "software":"information technology","oil and gas":"oil & gas","airlines":"air transport service",
         "aviation":"air transport service","automobiles":"automobile","auto":"automobile",
         "banking":"banks","bank":"banks","financial services":"finance",
         "pharmaceutical":"pharmaceuticals","pharma":"pharmaceuticals",
         "gems and jewellery":"gems, jewellery & watches","jewellery":"gems, jewellery & watches"}

def _number(value):
    return type(value) in (int,float) and isfinite(value)

def _observation(row,key,label,source,unit,today,max_age):
    try:
        if row.get("status")!="AVAILABLE":
            return None
        day=date.fromisoformat(row["as_of"])
        value=row.get("rate") if key in GROUPS["CURRENCIES"] else row.get("value")
        if not _number(value) or not 0<value<=1e9 or not 0<=(today-day).days<=max_age:
            return None
        selected=[x for x in row.get("changes",[]) if x.get("observations")==5]
        change=None
        if len(selected)==1:
            x=selected[0]
            start=date.fromisoformat(x["start_date"])
            end=date.fromisoformat(x["end_date"])
            delta=x.get("value") if key in GROUPS["OIL"]+GROUPS["US_YIELDS"] else x.get("percent")
            correct_unit=key not in GROUPS["OIL"]+GROUPS["US_YIELDS"] or x.get("unit")==unit
            if correct_unit and end==day and 1<=(end-start).days<=14 and _number(delta) and abs(delta)<=1e9:
                change={"start_date":start.isoformat(),"end_date":end.isoformat(),"value":delta,"unit":unit}
        return {"key":key,"label":label,"source":source,"as_of":day.isoformat(),"change":change}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return None

def _unique(rows,key_field,key):
    matches=[r for r in rows if isinstance(r,dict) and r.get(key_field)==key]
    return matches[0] if len(matches)==1 else {}

def summarize(snapshot,today):
    observations={}
    if snapshot.get("enabled") is True:
        fx=(snapshot.get("global_fx") or {}).get("items",[])
        macro=(snapshot.get("global_macro") or {}).get("sources",[])
        markets=(snapshot.get("global_markets") or {}).get("items",[])
        for key in GROUPS["CURRENCIES"]:
            row=_unique(fx,"pair",key)
            basis="ECB reference" if key.startswith("EUR_") else "ECB derived cross-rate"
            found=_observation(row,key,key.replace("_","/"),basis,"PERCENT",today,5)
            if found:
                observations[key]=found
        for kind,group in (("OIL","OIL"),("YIELDS","US_YIELDS")):
            section=_unique(macro,"source",global_macro.SOURCES[kind])
            for key in GROUPS[group]:
                row=_unique(section.get("items",[]),"series",key)
                found=_observation(row,key,global_macro.FIELDS[kind][key],global_macro.SOURCES[kind],
                    "BASIS_POINTS" if kind=="YIELDS" else "PERCENT",today,10 if kind=="OIL" else 5)
                if found:
                    observations[key]=found
        for key,(label,source,_,_,_) in global_markets.FIELDS.items():
            found=_observation(_unique(markets,"series",key),key,label,source,"PERCENT",today,7)
            if found:
                observations[key]=found
    groups=[{"group":g,"total_count":len(keys),"available_count":sum(k in observations for k in keys),
             "items":[observations[k] for k in keys if k in observations]} for g,keys in GROUPS.items()]
    count=len(observations)
    return {"status":"DISABLED" if not snapshot.get("enabled") else "AVAILABLE" if count==TOTAL else "PARTIAL" if count else "UNAVAILABLE",
            "available_count":count,"total_count":TOTAL,"groups":groups,"notice":NOTICE}

def _exposure(item,observations,instant):
    result={"status":"COMPANY_SECTOR_UNAVAILABLE","questions":[],"missing_factors":[],"notice":EXPOSURE_NOTICE}
    company=item.get("company_evidence") or {}
    if not exact_isin(item.get("isin")) or company.get("isin")!=item["isin"]:
        return result
    try:
        profile=(company.get("sections") or {}).get("profile") or {}
        source=profile.get("source") or {}
        stamp=datetime.fromisoformat(source["retrieved_at"])
        if (profile.get("status")!="AVAILABLE" or source.get("provider")!="UPSTOX" or stamp.tzinfo is None
                or not timedelta(0)<=instant-stamp<=timedelta(hours=24)):
            return result
        data=profile["data"]
        sector=data.get("sector")
        industry=data.get("industry")
        if not isinstance(sector,str) or not sector.strip() or len(sector)>180:
            return result
        normalized=" ".join(sector.casefold().split())
        rules=QUESTIONS.get(ALIASES.get(normalized,normalized))
        result.update(status="SECTOR_UNMAPPED",sector=sector,industry=industry if isinstance(industry,str) and len(industry)<=180 else None)
        if not rules:
            return result
        for key,question in rules.items():
            row=observations.get(key)
            if not row or not row["change"]:
                result["missing_factors"].append(key)
            else:
                result["questions"].append({"factor":key,"indicator":row["label"],"as_of":row["as_of"],
                                            "change":row["change"],"question":question})
        result["status"]="SECTOR_QUESTIONS_ONLY" if result["questions"] else "GLOBAL_EVIDENCE_MISSING"
        return result
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return result

def attach(snapshot,instant=None):
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    report=summarize(snapshot,today)
    snapshot["global_context"]=report
    if not snapshot.get("enabled"):
        return snapshot
    observations={item["key"]:item for group in report["groups"] for item in group["items"]}
    from .automatic_company_evidence import identify
    for item,_ in identify(snapshot):
        item["global_exposure"]=_exposure(item,observations,instant)
    return snapshot
