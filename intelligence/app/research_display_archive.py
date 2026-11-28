"""Bounded public historical observations for display only.

No candidate IDs, scores, recommendations, targets, AI commentary, raw holdings
or credentials enter this archive. Current consumers never read this table.
"""
from contextlib import closing
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from math import isfinite
import json,os,re,sqlite3

IST=ZoneInfo("Asia/Kolkata")
MAX_AGE=timedelta(days=7)
NOTICE="Last valid historical observations only. Not current candidates, prices, rankings or recommendations."
VERSION="DISPLAY_OBSERVATIONS_1"

def permitted():
    return os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def project(section,result,today):
    if not isinstance(result,dict):return []
    equity=section in ("NSE","BSE")
    if equity:
        source=result.get("momentum_leaders") or []
    else:
        source=(result.get("historical_coverage") or {}).get("items") or []
    if not isinstance(source,list):return []
    rows=[];seen=set()
    for row in source[:5]:
        try:
            name=row["symbol" if equity else "scheme_name"]
            day=row["as_of" if equity else "nav_date"]
            value=row["momentum_20d_percent" if equity else "cagr_3y_percent"]
            if (not isinstance(name,str) or not 1<=len(name)<=300 or any(ord(c)<32 for c in name)
                or type(value) not in (int,float) or not isfinite(value) or abs(value)>1e6
                or not (1 if equity else 0)<=(today-date.fromisoformat(day)).days<=(4 if equity else 7)):
                continue
            if equity and (row.get("exchange")!=section or not re.fullmatch(r"[A-Z0-9._&-]{1,40}",name)):continue
            if not equity and day!=(result.get("historical_coverage") or {}).get("comparison_date"):continue
            if (name,day) in seen:continue
            seen.add((name,day))
            rows.append({"label":name,"observed_date":day,"value_percent":value})
        except (KeyError,TypeError,ValueError,AttributeError,OverflowError):
            continue
    return rows

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS research_display_archive(
      section TEXT PRIMARY KEY,generated_at TEXT NOT NULL,methodology TEXT NOT NULL,payload TEXT NOT NULL)""")

def capture(db,section,result,instant,valid):
    # The caller supplies the original published evidence date gate.
    if not permitted() or not valid:return
    rows=project(section,result,instant.astimezone(IST).date())
    if not rows:return
    _table(db)
    db.execute("""INSERT INTO research_display_archive VALUES(?,?,?,?)
      ON CONFLICT(section) DO UPDATE SET generated_at=excluded.generated_at,
        methodology=excluded.methodology,payload=excluded.payload
      WHERE excluded.generated_at>=research_display_archive.generated_at""",
      (section,instant.isoformat(),VERSION,json.dumps(rows,allow_nan=False)))

def display(connect,snapshot,instant):
    if not snapshot.get("enabled") or not permitted():return []
    today=instant.astimezone(IST).date()
    sections={s["section"]:s for s in snapshot["sections"]}
    out=[]
    try:
        with closing(connect()) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='research_display_archive'").fetchone():return []
            for saved in db.execute("SELECT * FROM research_display_archive ORDER BY section"):
                try:
                    key=saved["section"];current=sections.get(key)
                    if not current or current["status"] not in ("READY","FAILED","STALE"):continue
                    if current["status"]=="READY" and project(key,current.get("result"),today):continue
                    stamp=datetime.fromisoformat(saved["generated_at"])
                    if saved["methodology"]!=VERSION or stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=MAX_AGE:continue
                    rows=json.loads(saved["payload"])
                    if not isinstance(rows,list) or not 1<=len(rows)<=5:continue
                    # Revalidate the compact stored shape and original dates, never extend them.
                    equity=key in ("NSE","BSE")
                    if any(not isinstance(x,dict) or set(x)!={"label","observed_date","value_percent"}
                           or not isinstance(x["label"],str) or not 1<=len(x["label"])<=300
                           or any(ord(c)<32 for c in x["label"])
                           or (equity and not re.fullmatch(r"[A-Z0-9._&-]{1,40}",x["label"]))
                           or type(x["value_percent"]) not in (int,float) or not isfinite(x["value_percent"]) or abs(x["value_percent"])>1e6
                           or not (1 if equity else 0)<=(stamp.astimezone(IST).date()-date.fromisoformat(x["observed_date"])).days<=(4 if equity else 7)
                           for x in rows):continue
                    out.append({"section":key,"status":"HISTORICAL_DISPLAY_ONLY","generated_at":stamp.isoformat(),
                        "current_status":current["status"],"metric":"20_SESSION_PRICE_CHANGE" if equity else "3_YEAR_CAGR",
                        "observations":rows,"qualification_eligible":False,"notice":NOTICE})
                except (KeyError,TypeError,ValueError,AttributeError,OverflowError):continue
    except (OSError,sqlite3.Error):return []
    return out
