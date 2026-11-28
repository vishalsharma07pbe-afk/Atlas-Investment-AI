"""Authorized operator-normalized official-export inputs, not independent authentication.

No guessed provider endpoints or price-index substitution. Read-only local file,
bounded data, explicit scheme identities, actual NAV/TRI anchor-date equality.
"""
from datetime import date,timedelta
from hashlib import sha256
from math import isfinite,sqrt
from pathlib import Path
from statistics import mean,median,stdev
import csv
import io
from decimal import Decimal, InvalidOperation
import json
import os
import re
import stat

VERSION="MF-LOCAL-TRI-1"
PATH=Path("/app/fund-evidence/evidence.json")
MAX_BYTES=4_000_000
INDEXES=("NIFTY 50 TRI","NIFTY 100 TRI","NIFTY MIDCAP 150 TRI","NIFTY SMALLCAP 250 TRI","NIFTY 500 TRI","NIFTY LARGEMIDCAP 250 TRI","NIFTY MULTICAP 50:25:25 TRI","NIFTY NEXT 50 TRI")
SEGMENTS={"LARGE_CAP":"NIFTY 100 TRI","MID_CAP":"NIFTY MIDCAP 150 TRI","SMALL_CAP":"NIFTY SMALLCAP 250 TRI"}
TRI_SOURCE="https://www.niftyindices.com/reports/historical-data"
AMFI_SOURCE="https://www.amfiindia.com/ter-of-mf-schemes"
AMFI_DISCLOSURE="https://www.amfiindia.com/research-information/amfi-data"
RISKOMETERS=("LOW","LOW_TO_MODERATE","MODERATE","MODERATELY_HIGH","HIGH","VERY_HIGH")
NOTICE=("Operator-supplied normalized official-export evidence; original publisher files and exact scheme mapping "
        "must be authenticated by the operator. File checks verify format and date alignment, not publisher authenticity "
        "or historical benchmark mandate. Comparisons use exact matched weekly observed NAV and gross total-return index dates. "
        "No price-index substitution, prediction, official rating or qualification promotion.")

def permitted():
    return os.getenv("ATLAS_MF_LOCAL_EVIDENCE_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def num(x,lo,hi):return type(x) in (int,float) and isfinite(x) and lo<=x<=hi

def day(v):
    if not isinstance(v,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",v):raise ValueError("DATE")
    return date.fromisoformat(v)

def unique(pairs):
    obj={}
    for k,v in pairs:
        if k in obj:raise ValueError("DUPLICATE_KEY")
        obj[k]=v
    return obj

def parse(raw,today):
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ValueError("SIZE")
    data=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda v: (_ for _ in ()).throw(ValueError("NONFINITE")))
    if not isinstance(data,dict) or data.get("schema")!=VERSION or data.get("authorization_attested") is not True:raise ValueError("SCHEMA")
    indexes=data.get("indices");schemes=data.get("schemes")
    if not isinstance(indexes,list) or len(indexes)>len(INDEXES) or not isinstance(schemes,list) or len(schemes)>1000:raise ValueError("LIMIT")
    out={};disclosures={}
    for i in indexes:
        name=i["benchmark"]
        if name not in INDEXES or name in out or i.get("source_url")!=TRI_SOURCE or i.get("series_type")!="GROSS_TOTAL_RETURN_INDEX":raise ValueError("INDEX_IDENTITY")
        rows=i["observations"]
        if not isinstance(rows,list) or not 157<=len(rows)<=2000:raise ValueError("INDEX_LENGTH")
        values={};prior=None
        for r in rows:
            d=day(r["date"]);v=r["tri"]
            if d>today or d<today-timedelta(days=2000) or prior is not None and d<=prior or not num(v,.000001,1e12):raise ValueError("INDEX_ROW")
            values[d]=v;prior=d
        out[name]=values
    for s in schemes:
        code=s["scheme_code"];isin=s["isin_growth"]
        if type(code) is not int or not 1<=code<=999999999 or code in disclosures or not isinstance(isin,str) or not re.fullmatch(r"INF[A-Z0-9]{9}",isin) or s.get("plan")!="DIRECT" or s.get("option")!="GROWTH":raise ValueError("SCHEME_IDENTITY")
        if s.get("source_url")!=AMFI_DISCLOSURE or s.get("ter_source_url")!=AMFI_SOURCE or s.get("benchmark") not in INDEXES:raise ValueError("DISCLOSURE_SOURCE")
        d=day(s["disclosure_date"]);td=day(s["ter_date"]);rd=day(s["riskometer_date"])
        if not all(x<=today for x in (d,td,rd)) or td>d or rd>d or s.get("riskometer") not in RISKOMETERS or not num(s.get("ter_percent"),0,100):raise ValueError("DISCLOSURE_ROW")
        disclosures[code]={k:s[k] for k in ("scheme_code","isin_growth","plan","option","benchmark","source_url","ter_source_url","disclosure_date","ter_date","ter_percent","riskometer_date","riskometer")}
    if len({s["isin_growth"] for s in disclosures.values()})!=len(disclosures):raise ValueError("DUPLICATE_ISIN")
    return {"indices":out,"schemes":disclosures,"sha256":sha256(raw).hexdigest()}

def load(today,path=PATH):
    if not permitted():return {"status":"DISABLED_OR_NOT_AUTHORIZED"}
    try:
        # Reject symlinks and nonregular input. Bound actual reads even if file
        # changes after stat; no uploaded network URLs are followed.
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,"rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):raise ValueError("FILE_TYPE")
            raw=f.read(MAX_BYTES+1)
        return {"status":"LOCAL_EXPORTS_LOADED",**parse(raw,today)}
    except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError):return {"status":"MISSING_OR_INVALID_LOCAL_EXPORTS"}

TER_PATH=PATH.with_name("ter-components.csv")
TER_FIELDS=("scheme_code","isin_growth","plan","option","ter_date","base_expense_percent",
    "brokerage_percent","transaction_percent","statutory_levies_percent","ter_percent")

def parse_ter(raw,today):
    """Operator-normalized exact scheme rows; not a claimed AMFI CSV schema."""
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise ValueError("SIZE")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig"),newline=""),strict=True)
    if tuple(reader.fieldnames or ())!=TER_FIELDS:raise ValueError("TER_SCHEMA")
    out={};isins=set()
    for row in reader:
        if None in row or any(v is None for v in row.values()):raise ValueError("TER_ROW")
        code=row["scheme_code"];isin=row["isin_growth"];d=day(row["ter_date"])
        if not re.fullmatch(r"[1-9][0-9]{0,8}",code) or not re.fullmatch(r"INF[A-Z0-9]{9}",isin) or row["plan"]!="DIRECT" or row["option"]!="GROWTH" or d>today or code in out or isin in isins:raise ValueError("TER_IDENTITY")
        values={}
        for key in TER_FIELDS[5:]:
            if not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,6})?",row[key]):raise ValueError("TER_NUMBER")
            value=Decimal(row[key])
            if not Decimal(0)<=value<=Decimal(100):raise ValueError("TER_NUMBER")
            values[key]=value
        # Published values rounded independently can differ by <=0.0002 pp.
        # Do not calculate a missing total or substitute BER for TER.
        if abs(sum(values[k] for k in TER_FIELDS[5:-1])-values["ter_percent"])>Decimal("0.0002"):
            raise ValueError("TER_COMPONENT_MISMATCH")
        out[code]={"scheme_code":int(code),"isin_growth":isin,"plan":"DIRECT","option":"GROWTH",
            "ter_date":d.isoformat(),**{k:float(v) for k,v in values.items()}}
        isins.add(isin)
        if len(out)>1000:raise ValueError("TER_LIMIT")
    return {"status":"LOCAL_TER_COMPONENTS_LOADED","items":out,"sha256":sha256(raw).hexdigest()}

def load_ter(today,path=TER_PATH):
    if not permitted():return {"status":"DISABLED_OR_NOT_AUTHORIZED","items":{}}
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,"rb") as f:
            before=os.fstat(f.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=MAX_BYTES:raise ValueError("SIZE")
            raw=f.read(MAX_BYTES+1);after=os.fstat(f.fileno())
            if len(raw)!=before.st_size or before.st_mtime_ns!=after.st_mtime_ns or before.st_size!=after.st_size:raise ValueError("FILE_CHANGED")
        return parse_ter(raw,today)
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,csv.Error,InvalidOperation):
        return {"status":"MISSING_OR_INVALID_LOCAL_TER","items":{}}

def annual(a,b,days):return 100*((b/a)**(365.2425/days)-1)

def compare(row,values):
    points=row.get("weekly_anchor_series");block=row.get("matched_weekly_comparison") or {}
    if not isinstance(points,list) or len(points)!=157 or block.get("methodology")!="MF-WEEKLY-MATCH-1":return None
    try:
        dates=[day(p["date"]) for p in points];nav=[p["nav"] for p in points]
        if any(not num(n,.000001,1e9) for n in nav) or any(not 4<=(b-a).days<=10 for a,b in zip(dates,dates[1:])) or dates[-1].isoformat()!=row["nav_date"]:return None
        if sha256("".join(d.isoformat()+"\n" for d in dates).encode()).hexdigest()!=block.get("date_digest"):return None
        if dates[0].isoformat()!=block.get("first_date") or dates[-1].isoformat()!=block.get("last_date"):return None
        # Require all 157 index dates, never forward-fill a missing index day.
        if any(d not in values for d in dates):return None
        tri=[values[d] for d in dates]
        diff=[annual(nav[i-52],nav[i],(dates[i]-dates[i-52]).days)-annual(tri[i-52],tri[i],(dates[i]-dates[i-52]).days) for i in range(52,157)]
        excess=[nav[i]/nav[i-1]-tri[i]/tri[i-1] for i in range(1,157)]
        windows=[]
        for n in (52,156):
            days=(dates[-1]-dates[-n-1]).days
            fund=annual(nav[-n-1],nav[-1],days);index=annual(tri[-n-1],tri[-1],days)
            windows.append({"weeks":n,"first_date":dates[-n-1].isoformat(),"last_date":dates[-1].isoformat(),"fund_cagr_percent":round(fund,4),"tri_cagr_percent":round(index,4),"difference_pp":round(fund-index,4)})
        tracking=100*sqrt(52)*stdev(excess)
        if not all(num(x,-1e9,1e9) for x in [tracking,*diff,*[w[k] for w in windows for k in ("fund_cagr_percent","tri_cagr_percent","difference_pp")]]):return None
        return {"status":"MATCHED_LOCAL_TRI_EXPORT","matched_anchors":157,"rolling_windows":105,
            "above_tri_windows":sum(d>0.00005 for d in diff),"above_tri_percent":round(100*sum(d>0.00005 for d in diff)/105,4),
            "median_rolling_difference_pp":round(median(diff),4),"worst_rolling_difference_pp":round(min(diff),4),
            "annualized_weekly_active_volatility_percent":round(tracking,4),"windows":windows}
    except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError):return None

def reports(candidates,source_rows,loaded,today,ter=None):
    result={}
    ter=ter or {}
    if loaded.get("status")!="LOCAL_EXPORTS_LOADED" and ter.get("status")!="LOCAL_TER_COMPONENTS_LOADED":return result
    by_code={}
    conflicts=set()
    for r in source_rows:
        if not isinstance(r,dict) or type(r.get("scheme_code")) is not int:continue
        code=str(r["scheme_code"])
        if code in by_code:conflicts.add(code)
        by_code[code]=r
    for f in candidates:
        r=by_code.get(f.identifier) or {}
        if not f.identifier.isdigit() or f.identifier in conflicts:continue
        if f.plan!="DIRECT" or f.option!="GROWTH":continue
        s=loaded.get("schemes",{}).get(int(f.identifier))
        c=(ter.get("items") or {}).get(f.identifier)
        if s and (s["isin_growth"]!=r.get("isin_growth") or not 0<=(today-day(s["disclosure_date"])).days<=60):s=None
        if c and (c["isin_growth"]!=r.get("isin_growth") or not 0<=(today-day(c["ter_date"])).days<=7):c=None
        if not s and not c:continue
        disclosure={**s} if s else {"scheme_code":int(f.identifier),"isin_growth":c["isin_growth"],"plan":"DIRECT","option":"GROWTH",
            "benchmark":None,"disclosure_date":None,"ter_date":None,"ter_percent":None,"riskometer":None,
            "riskometer_date":None,"source_url":None,"ter_source_url":AMFI_SOURCE}
        if s and (today-day(s["ter_date"])).days>90:disclosure.update(ter_date=None,ter_percent=None)
        if s and (today-day(s["riskometer_date"])).days>60:disclosure.update(riskometer_date=None,riskometer=None)
        ter_evidence=None
        if c:
            if disclosure["ter_date"]==c["ter_date"] and disclosure["ter_percent"] is not None and abs(disclosure["ter_percent"]-c["ter_percent"])>.0002:
                disclosure.update(ter_date=None,ter_percent=None)
                ter_evidence={"status":"CONFLICTING_SAME_DATE_TER","source_sha256":ter["sha256"]}
            elif disclosure["ter_date"] is None or c["ter_date"]>=disclosure["ter_date"]:
                disclosure.update(ter_date=c["ter_date"],ter_percent=c["ter_percent"])
                ter_evidence={"status":"OPERATOR_NORMALIZED_TER_COMPONENTS",**c,"source_sha256":ter["sha256"]}
        benchmark=disclosure["benchmark"]
        index=loaded.get("indices",{}).get(benchmark,{})
        comparison=compare(r,index) if benchmark else None
        provenance=(loaded.get("downloaded_tri_provenance") or {}).get(benchmark)
        if comparison and provenance:comparison={**comparison,"status":"MATCHED_AUTHORIZED_DIRECT_TRI_CSV","source_provenance":provenance}
        elif comparison and (loaded.get("operator_tri_provenance") or {}).get(benchmark):
            comparison={**comparison,"source_provenance":loaded["operator_tri_provenance"][benchmark]}
        result[f.identifier]={"status":"LOCAL_EXPORT_EVIDENCE_ONLY","disclosure":disclosure,"benchmark_comparison":comparison,
            "input_sha256":loaded.get("sha256"),"ter_components_evidence":ter_evidence,"notice":NOTICE}
    return result

def overview(loaded,today):
    result=[]
    for category,name in SEGMENTS.items():
        values=loaded.get("indices",{}).get(name,{})
        item={"segment":category,"status":"UNAVAILABLE","benchmark":None,"period":None,"last_available_date":None,"evidence":[],"blocker":"BENCHMARK_TRI_NOT_CONNECTED"}
        if values:
            last=max(values)
            if 0<=(today-last).days<=7:
                target=last-timedelta(weeks=52)
                prior=[d for d in values if target-timedelta(days=3)<=d<=target]
                if prior:
                    first=max(prior);cagr=annual(values[first],values[last],(last-first).days)
                    if num(cagr,-100,1e6):
                        item.update(status="LOCAL_TRI_EXPORT_OBSERVATION",benchmark=name,period="52 weeks",last_available_date=last.isoformat(),
                            evidence=["Annualized historical TRI return: "+str(round(cagr,4))+"%",
                                      "Authorized direct CSV; segment proxy only" if name in loaded.get("downloaded_tri_provenance",{}) else "Operator-supplied export; segment proxy only"],blocker=None)
                        if name in loaded.get("downloaded_tri_provenance",{}):item["status"]="AUTHORIZED_DIRECT_TRI_OBSERVATION"
        result.append(item)
    return result
