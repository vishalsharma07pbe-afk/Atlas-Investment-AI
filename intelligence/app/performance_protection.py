"""Sticky local research allocation holds, independent of temporary source gaps.

Only a mature, comparable positive observation of the SAME policy releases an
existing adverse hold. No order execution, private data, or model fitting.
"""
from contextlib import closing
from . import decision_quality as q

VERSION="ALLOCATION-PROTECTION-1"
SCOPES=("STOCK","EARNINGS","LARGE_CAP","MID_CAP","SMALL_CAP")
NOTICE="Adverse observed performance persists through missing or unavailable evidence. A subsequent sufficiently covered positive comparison can release the research hold; this is not validation or a recommendation."

def observations(report):
    states={}
    stock=q.obj(q.obj(q.obj(report.get("decision_outcomes")).get("states")).get("PRIORITY_RESEARCH"))
    if not q.obj(report.get("decision_outcomes")).get("truncated"):
        if stock.get("status")=="ADVERSE_OBSERVED_SAMPLE":states["STOCK"]="ADVERSE"
        elif stock.get("status")=="POSITIVE_DESCRIPTIVE_SAMPLE":states["STOCK"]="POSITIVE"
    review=q.obj(report.get("forecast_model_review"))
    if review.get("status")=="MATURE_MODEL_COMPARISON":
        baseline=next((x for x in q.rows(review.get("models")) if isinstance(x,dict) and x.get("model")=="PERSISTENCE"),{})
        if baseline.get("status")=="REVIEW_WEAK_BASELINE":states["EARNINGS"]="ADVERSE"
        elif baseline.get("status")=="CONSISTENT_DESCRIPTIVE_IMPROVEMENT":states["EARNINGS"]="POSITIVE"
    funds=q.obj(report.get("fund_decision_outcomes"))
    for category in SCOPES[2:]:
        group=q.obj(funds.get(category));state=q.obj(q.obj(group.get("states")).get("PRIORITY_RESEARCH")).get("tri_review_status")
        if group.get("truncated"):continue
        if state=="ADVERSE_DESCRIPTIVE_SAMPLE":states[category]="ADVERSE"
        elif state=="POSITIVE_DESCRIPTIVE_SAMPLE":states[category]="POSITIVE"
    return states

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS allocation_protection_state(
        policy TEXT NOT NULL,scope TEXT NOT NULL,state TEXT NOT NULL,observed_at TEXT NOT NULL,PRIMARY KEY(policy,scope))""")

def update(report,connect,instant):
    if report.get("status")!="RESEARCH_AVAILABLE":return
    stamp=instant.isoformat()
    with closing(connect()) as db,db:
        _table(db)
        for scope,state in observations(report).items():
            db.execute("""INSERT INTO allocation_protection_state VALUES(?,?,?,?)
                ON CONFLICT(policy,scope) DO UPDATE SET state=excluded.state,observed_at=excluded.observed_at
                WHERE excluded.observed_at>allocation_protection_state.observed_at""",(VERSION,scope,state,stamp))

def attach(report,connect):
    if report.get("status")!="RESEARCH_AVAILABLE":return
    saved={}
    with closing(connect()) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='allocation_protection_state'").fetchone():
            saved={r["scope"]:r["state"] for r in db.execute("SELECT * FROM allocation_protection_state WHERE policy=?",(VERSION,)) if r["scope"] in SCOPES and r["state"] in ("ADVERSE","POSITIVE")}
    current=observations(report)
    # A fresh adverse sample always takes effect immediately; a positive
    # sample only releases a persisted hold after the scheduled update.
    held=[s for s in SCOPES if saved.get(s)=="ADVERSE" or current.get(s)=="ADVERSE"]
    report["performance_protection"]={"methodology":VERSION,"status":"ACTIVE_HOLDS" if held else "NO_OBSERVED_HOLD","held_scopes":held,"current_observations":current,"notice":NOTICE,"qualified":False}
    policy=report.setdefault("decision_quality",{})
    if "STOCK" in held:policy["stock_allocation_hold"]="PERSISTED_ADVERSE_STOCK_SAMPLE"
    if "EARNINGS" in held:policy["forecast_allocation_hold"]="PERSISTED_ADVERSE_EARNINGS_SAMPLE"
    categories=[s for s in SCOPES[2:] if s in held]
    if categories:policy["fund_allocation_holds"]=categories
    for r in q.rows(report.get("stocks")):
        if ("STOCK" in held or "EARNINGS" in held) and r.get("action")=="RESEARCH_FOR_ENTRY":r["action"]="WATCH_FOR_CONFIRMATION"
    for g in q.rows(report.get("funds")):
        if "EARNINGS" in held or g.get("category") in categories:
            for r in q.rows(g.get("items")):
                if r.get("action")=="COMPARE_FOR_SIP":r["action"]="WATCH_FOR_CONFIRMATION"
    if held:
        report.setdefault("next_steps",[]).insert(0,"Research allocation protection remains active for "+", ".join(held)+". Reassess after comparable positive evidence.")
