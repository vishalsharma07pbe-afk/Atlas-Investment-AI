"""Source-linked issuer financial observations from authorized NSE archive links.

The exchange website index contract is not live verified. Accept only a local
public link manifest, fetch and parse automatically; no manual financial values,
guessed links, private data, or standalone/consolidated substitutions.
"""
from calendar import monthrange
from contextlib import closing
from datetime import date,datetime,timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import json
import os
import re
import stat
import httpx
from .nse_pledge_filings import Tables, fetch
from .replay_evidence import exact_isin
from .automatic_company_evidence import identify_priority
from .company_venues import collect

IST=ZoneInfo("Asia/Kolkata")
PATH=Path("/app/filing-reports/financial-links.json")
INTERVAL=900
MAX_BYTES=5_000_000
DECLARATION="Declaration of unmodified opinion or statement on impact of audit qualification"
PERIOD_START="Date of start of reporting period"
PERIOD_END="Date of end of reporting period"
SCOPE="Nature of report standalone or consolidated"
AUDITED="Whether results are audited or unaudited"
NOTICE=("Issuer-reported consolidated Ind-AS results from the supplied official exchange archive link. "
        "Quarter and financial-year-to-date figures are separate. Audit declaration is issuer-reported, not an independent "
        "reading of the signed audit report. Missing or newer filings are not excluded by this sample. "
        "Cross-source revenue is a comparison prompt; provider revenue definition and rounding may differ. No valuation or clearance.")

def permitted():
    return os.getenv("ATLAS_NSE_FINANCIAL_FILINGS_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def valid_url(url):
    if not isinstance(url,str) or len(url)>300:return False
    p=urlsplit(url)
    return p.scheme=="https" and p.netloc=="nsearchives.nseindia.com" and not p.query and not p.fragment and bool(
        re.fullmatch(r"/corporate/ixbrl/INTEGRATED_FILING_INDAS_[0-9]+_[0-9]{14}_iXBRL_WEB\.html",p.path))

def fresh_period(day,today):
    return day.month in (3,6,9,12) and day.day==monthrange(day.year,day.month)[1] and 0<=(today-day).days<=150

def manifest(payload,today):
    if len(payload)>500000:raise ValueError("FINANCIAL_MANIFEST_SIZE")
    obj=json.loads(payload)
    if not isinstance(obj,list) or len(obj)>2000:raise ValueError("FINANCIAL_MANIFEST_SCHEMA")
    result={}
    for r in obj:
        if not isinstance(r,dict) or set(r)!={"isin","period","url"} or not exact_isin(r["isin"]) or not valid_url(r["url"]):
            raise ValueError("FINANCIAL_MANIFEST_IDENTITY")
        day=date.fromisoformat(r["period"])
        if not fresh_period(day,today):raise ValueError("FINANCIAL_MANIFEST_PERIOD")
        if r["isin"] in result:raise ValueError("FINANCIAL_MANIFEST_DUPLICATE")
        result[r["isin"]]=(day,r["url"])
    return result

def read_manifest(today,path=PATH):
    try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except FileNotFoundError:return {}
    with os.fdopen(fd,"rb") as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size>500000:raise ValueError("FINANCIAL_MANIFEST_FILE")
        raw=stream.read(500001)
        after=os.fstat(stream.fileno())
        if before.st_mtime_ns!=after.st_mtime_ns or before.st_size!=after.st_size or len(raw)!=after.st_size:
            raise ValueError("FINANCIAL_MANIFEST_CHANGED")
    return manifest(raw,today)

def number(raw):
    # Indian/western thousands separators and parenthesized negatives, no
    # currencies, blanks, dashes, scientific notation or inferred zero.
    if not isinstance(raw,str) or not re.fullmatch(r"(?:-?[0-9][0-9,]*(?:\.[0-9]{1,8})?|\([0-9][0-9,]*(?:\.[0-9]{1,8})?\))",raw):raise ValueError("FINANCIAL_NUMBER")
    negative=raw.startswith("(")
    text=raw.strip("()")
    integer=text.split(".")[0].lstrip("-")
    if "," in integer and not (re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+",integer) or re.fullmatch(r"[0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3}",integer)):
        raise ValueError("FINANCIAL_GROUPING")
    v=Decimal(text.replace(",",""))
    if abs(v)>Decimal("1e15"):raise ValueError("FINANCIAL_RANGE")
    return -v if negative else v

def day(raw):
    return datetime.strptime(raw,"%d-%m-%Y").date()

def pairs(table):
    return [(r[0],r[1]) for r in table if len(r)==2]

def field(table,label,width):
    # Rendered exchange tables can include an explicit blank/ordinal cell.
    found=[]
    for r in table:
        if len(r)==width+1 and r[0]==label:found.append(r[1:])
        elif len(r)==width+2 and r[1]==label and re.fullmatch(r"[A-Za-z0-9(). ]{0,12}",r[0]):found.append(r[2:])
    if len(found)!=1:raise ValueError("FINANCIAL_FIELD_AMBIGUOUS")
    return found[0]

METRICS={"revenue":"Revenue from operations","other_income":"Other income","total_income":"Total income",
         "expenses":"Total expenses","profit_before_tax":"Total profit before tax","total_tax":"Total tax expenses",
         "continuing_profit":"Net Profit Loss for the period from continuing operations","net_profit":"Total profit (loss) for period",
         "owners_profit":"Profit or loss, attributable to owners of parent"}

def parse(payload,isin,expected,today):
    if not exact_isin(isin) or not fresh_period(expected,today) or not 0<len(payload)<=MAX_BYTES:raise ValueError("FINANCIAL_IDENTITY")
    parser=Tables();parser.feed(payload.decode("utf-8-sig"));parser.close()
    if parser.stack:raise ValueError("FINANCIAL_UNCLOSED_TABLE")
    meta_tables=[t for t in parser.tables if ("ISIN",isin) in pairs(t)]
    if len(meta_tables)!=1:raise ValueError("FINANCIAL_METADATA")
    meta=meta_tables[0]
    def m(key):return field(meta,key,1)[0]
    if (m("ISIN")!=isin or m("Class of security")!="Equity" or m("Type of company")!="Main Board"
        or m("Description of presentation currency")!="INR" or m("Level of rounding used in financial results")!="Lakhs"
        or m("Reporting Type")!="Quarterly" or m(SCOPE)!="Consolidated"):raise ValueError("FINANCIAL_SCOPE")
    fy=date(expected.year if expected.month>=4 else expected.year-1,4,1)
    end_fy=date(fy.year+1,3,31)
    qstart=date(expected.year,expected.month-2,1)
    board=day(m("Date of board meeting when results were approved"))
    qname={6:"First quarter",9:"Second quarter",12:"Third quarter",3:"Fourth quarter"}[expected.month]
    if day(m("Date of start of financial year"))!=fy or day(m("Date of end of financial year"))!=end_fy or m("Reporting Quarter")!=qname or not expected<=board<=today:
        raise ValueError("FINANCIAL_METADATA_PERIOD")
    # Match one statement containing the complete numeric leaf names, not
    # segment/OCI tables with similar period headers.
    statements=[t for t in parser.tables if any(METRICS["net_profit"] in r for r in t) and any(METRICS["revenue"] in r for r in t)]
    if len(statements)!=1:raise ValueError("FINANCIAL_STATEMENT_AMBIGUOUS")
    table=statements[0]
    if field(table,PERIOD_START,2)!=[qstart.strftime("%d-%m-%Y"),fy.strftime("%d-%m-%Y")] or field(table,PERIOD_END,2)!=[expected.strftime("%d-%m-%Y")]*2 or field(table,SCOPE,2)!=["Consolidated"]*2:
        raise ValueError("FINANCIAL_PERIOD_MISMATCH")
    audit=field(table,AUDITED,2)
    if any(v not in ("Audited","Unaudited") for v in audit) or audit!=[m("Whether results are audited or unaudited for the quarter ended"),m("Whether results are audited or unaudited for the Year to date for current period ended/year ended")]:
        raise ValueError("FINANCIAL_AUDIT_SCOPE")
    data={k:[number(v) for v in field(table,label,2)] for k,label in METRICS.items()}
    # Up to 2 lakhs per identity permits displayed rounding; never silently
    # fix a conflicting filing. Retain reported total and parent profit separately.
    for i in (0,1):
        if data["revenue"][i]<0 or abs(data["revenue"][i]+data["other_income"][i]-data["total_income"][i])>2 or abs(data["profit_before_tax"][i]-data["total_tax"][i]-data["continuing_profit"][i])>2:
            raise ValueError("FINANCIAL_RECONCILIATION")
    declaration=m(DECLARATION)
    if declaration not in ("Declaration of unmodified opinion","Statement on impact of audit qualification",""):raise ValueError("FINANCIAL_AUDIT_DECLARATION")
    detail=[t for t in parser.tables if any(r and r[0]=="Auditor's opinion" for r in t)]
    opinion="NOT_ESTABLISHED"
    if declaration=="Statement on impact of audit qualification":
        opinion="ISSUER_REPORTED_AUDIT_QUALIFICATION"
        if len(detail)==1:
            stated=field(detail[0],"Auditor's opinion",1)[0]
            if stated in ("Qualified opinion","Adverse opinion","Disclaimer of opinion"):opinion=stated.upper().replace(" ","_")
    elif declaration=="Declaration of unmodified opinion":
        opinion="ISSUER_DECLARED_UNMODIFIED_NOT_SIGNED_REPORT_VERIFIED" if audit==["Audited"]*2 else "DECLARATION_PRESENT_UNAUDITED_PERIOD"
    if len(detail)>1:raise ValueError("FINANCIAL_AUDIT_DETAIL_AMBIGUOUS")
    def amounts(i):return {k:float(v[i]/100) for k,v in data.items()}
    # Cash-flow table is optional; only exact financial YTD window and basis.
    cash=None
    cfo_label="Net cash flows from (used in) operating activities"
    cash_tables=[t for t in parser.tables if any(cfo_label in r for r in t)]
    if len(cash_tables)==1:
        ct=cash_tables[0]
        try:
            if field(ct,PERIOD_START,1)==[fy.strftime("%d-%m-%Y")] and field(ct,PERIOD_END,1)==[expected.strftime("%d-%m-%Y")] and field(ct,SCOPE,1)==["Consolidated"] and field(ct,AUDITED,1)==[audit[1]]:
                cfo=number(field(ct,cfo_label,1)[0])/100
                profit=data["net_profit"][1]/100
                cash={"operating_cash_flow_cr":float(cfo),"net_profit_cr":float(profit),
                    "cash_to_profit_ratio":float(round(cfo/profit,4)) if profit>0 and abs(cfo/profit)<=10000 else None}
        except ValueError:pass
    return {"isin":isin,"period":expected.isoformat(),"board_approval_date":board.isoformat(),"scope":"CONSOLIDATED","units":"INR_CRORE",
        "quarter_start":qstart.isoformat(),"year_to_date_start":fy.isoformat(),"quarter_audit_status":audit[0],"year_to_date_audit_status":audit[1],
        "quarter":amounts(0),"year_to_date":amounts(1),"audit_opinion":opinion,"cash_flow_ytd":cash}

def load(isin,period,url,today):
    if not valid_url(url):raise ValueError("FINANCIAL_URL")
    with httpx.Client(timeout=20,follow_redirects=False) as client:raw=fetch(client,url)
    return {**parse(raw,isin,period,today),"source_url":url,"source_sha256":sha256(raw).hexdigest()}

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS nse_financial_filings(
      isin TEXT PRIMARY KEY,period TEXT NOT NULL,source_url TEXT NOT NULL,attempted_at TEXT NOT NULL,next_due TEXT NOT NULL,status TEXT NOT NULL,payload TEXT)""")

def refresh(snapshot,connect,instant,loader=load,path=PATH):
    if not snapshot.get("enabled") or not permitted():return False
    today=instant.astimezone(IST).date()
    links=read_manifest(today,path)
    observations=collect(snapshot,instant)
    targets={isin for item,isin in identify_priority(snapshot) if isin in links and any(r.get("as_of")==item.get("as_of") and r.get("id")==item.get("id") and r["exchange"]==item["exchange"] for r in observations.get(isin,[]))}
    stamp=instant.isoformat()
    with closing(connect()) as db,db:
        _table(db);db.execute("BEGIN IMMEDIATE")
        old={r["isin"]:r for r in db.execute("SELECT * FROM nse_financial_filings")}
        if any(r["status"] in ("RUNNING","UNAVAILABLE") and r["attempted_at"]>(instant-timedelta(hours=1)).isoformat() for r in old.values()):return False
        due=sorted((i for i in targets if i not in old or old[i]["next_due"]<=stamp or (old[i]["period"],old[i]["source_url"])!=(links[i][0].isoformat(),links[i][1])),
                   key=lambda i:(old[i]["attempted_at"] if i in old else "",i))
        if not due:return bool(targets)
        isin=due[0];period,url=links[isin]
        db.execute("""INSERT INTO nse_financial_filings VALUES(?,?,?,?,?,'RUNNING',NULL)
          ON CONFLICT(isin) DO UPDATE SET period=excluded.period,source_url=excluded.source_url,attempted_at=excluded.attempted_at,next_due=excluded.next_due,status='RUNNING',payload=NULL""",
          (isin,period.isoformat(),url,stamp,(instant+timedelta(hours=1)).isoformat()))
    result=None
    try:
        result=loader(isin,period,url,today)
        if result.get("isin")!=isin or result.get("period")!=period.isoformat() or result.get("source_url")!=url:result=None
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError,httpx.HTTPError,OSError):pass
    with closing(connect()) as db,db:
        _table(db)
        db.execute("UPDATE nse_financial_filings SET status=?,payload=?,next_due=? WHERE isin=? AND attempted_at=? AND status='RUNNING'",
           ("AVAILABLE" if result else "UNAVAILABLE",json.dumps(result,allow_nan=False) if result else None,
            (instant+timedelta(days=1) if result else instant+timedelta(hours=6)).isoformat(),isin,stamp))
    return result is not None

def compare(report,company):
    comparison={"status":"NOT_COMPARABLE","notice":"Only provider consolidated quarterly revenue vs issuer operating revenue, same period. Not verified identical definitions or source truth."}
    if not company or report["isin"]!=company.get("isin"):return comparison
    q=company.get("quarterly_financials") or {}
    if q.get("latest_period")!=report["period"]:return comparison
    rows=[r for r in q.get("items",[]) if r.get("metric")=="revenue"]
    if len(rows)!=1:return comparison
    v=rows[0].get("latest_value")
    from math import isfinite
    if type(v) not in (float,int) or not isfinite(v) or v<0:return comparison
    observed=report["quarter"]["revenue"]
    difference=round(v-observed,6)
    tolerance=max(0.1,abs(observed)*.01)
    return {**comparison,"status":"WITHIN_ILLUSTRATIVE_TOLERANCE" if abs(difference)<=tolerance else "REVENUE_DIFFERENCE_REVIEW",
            "provider_revenue_cr":v,"issuer_operating_revenue_cr":observed,"difference_cr":difference,"tolerance_cr":tolerance}

def attach(snapshot,connect,instant,path=PATH):
    summary={"status":"DISABLED_OR_NOT_AUTHORIZED","matched_companies":0,"notice":NOTICE}
    snapshot["independent_financial_filings"]=summary
    if not snapshot.get("enabled") or not permitted():return snapshot
    today=instant.astimezone(IST).date()
    links=read_manifest(today,path)
    with closing(connect()) as db:
        _table(db)
        saved={r["isin"]:r for r in db.execute("SELECT * FROM nse_financial_filings WHERE status='AVAILABLE' AND attempted_at BETWEEN ? AND ?",
            ((instant-timedelta(days=7)).isoformat(),instant.isoformat()))}
    matched=set()
    for item,isin in identify_priority(snapshot):
        item.pop("independent_financial_evidence",None)
        if isin not in links or isin not in saved:continue
        try:
            row=saved[isin];e=json.loads(row["payload"])
            period,url=links[isin]
            if e["isin"]!=isin or e["period"]!=period.isoformat() or e["source_url"]!=url:continue
        except (ValueError,TypeError,KeyError):continue
        item["independent_financial_evidence"]={**e,"retrieved_at":row["attempted_at"],"status":"REPORTED_CONSOLIDATED_FILING",
            "comparison":compare(e,item.get("company_evidence")),"notice":NOTICE}
        matched.add(isin)
    summary.update(status="REPORTED_FILINGS_AVAILABLE" if matched else "AWAITING_EVIDENCE" if links else "AWAITING_OFFICIAL_LINKS",matched_companies=len(matched),supplied_links=len(links))
    return snapshot
