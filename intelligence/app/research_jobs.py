"""Persistent bounded scheduler ledger for existing research functions.

One active claim per SQLite database. A finite lease recovers interrupted
attempts; this is a local single-worker coordinator, not a distributed exactly-
once execution guarantee. Existing provider-specific claims remain authoritative.
No private identities, inputs, results, or raw exception messages are stored.
"""
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

LEASE_SECONDS=1800
POLL_SECONDS=5
AUXILIARY=("PORTFOLIO_REVIEW","INSTITUTIONAL_FLOWS","WATCH_OUTCOMES",
           "COMPANY_EVIDENCE","COMPANY_NEWS","STRATEGY_REPLAY","AI_REVIEW")


def definitions(sections):
    return {"CALENDAR_CONTEXT":-10,"PORTFOLIO_REVIEW":0, **{"SECTION:"+s:10+i for i,s in enumerate(sections)},
            "INSTITUTIONAL_FLOWS":30,"WATCH_OUTCOMES":31,"COMPANY_EVIDENCE":32,
            "COMPANY_NEWS":33,"STRATEGY_REPLAY":34,"FUND_DISCLOSURES":35,"FUND_PORTFOLIOS":36,"FUND_COMPANY_EVIDENCE":37,"DEAL_REPORTS":38,"GLOBAL_FX":39,"AI_REVIEW":40,"GLOBAL_OIL":41,"GLOBAL_YIELDS":42,
            "GLOBAL_SP500":43,"GLOBAL_DJIA":44,"GLOBAL_NASDAQCOM":45,"GLOBAL_NIKKEI225":46,"GLOBAL_GOLD":47,"GLOBAL_SILVER":48,
            "RELEASE_FED":49,"RELEASE_ECB":50,"RELEASE_BLS_CPI":51,"RELEASE_BLS_PPI":52,"RELEASE_BLS_JOBS":53,"ECONOMIC_CALENDAR":54,"MARKET_REGIME":55,"PUBLIC_RESEARCH_ALERTS":56,"AMFI_EQUITY_CAP":57,"NSE_SURVEILLANCE":58,"NSE_PLEDGE_FILINGS":59,"NSE_FINANCIAL_FILINGS":60,"SECTOR_BENCHMARKS":61,"FUND_WATCH_OUTCOMES":62,"FUND_AI_REVIEW":63,"OFFICIAL_TRI_DOWNLOAD":64,"OFFICIAL_AMC_FACTSHEETS":65,"FORWARD_EARNINGS_BASELINE":66,"OFFICIAL_AMFI_TER":67,"INVESTMENT_ANALYST_AI":68}


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS research_job_state(
        job TEXT PRIMARY KEY, priority INTEGER NOT NULL, status TEXT NOT NULL,
        next_due REAL NOT NULL, attempted_at REAL, finished_at REAL,
        last_completed_at REAL, lease_until REAL, claim_id TEXT,
        failures INTEGER NOT NULL DEFAULT 0, interrupted INTEGER NOT NULL DEFAULT 0,
        error_code TEXT)""")


def claim(connect,jobs,instant):
    with closing(connect()) as db, db:
        _table(db)
        db.execute("BEGIN IMMEDIATE")
        for job,priority in jobs.items():
            db.execute("""INSERT INTO research_job_state(job,priority,status,next_due)
                VALUES(?,?,'PENDING',0) ON CONFLICT(job) DO UPDATE SET priority=excluded.priority""",(job,priority))
        db.execute("""UPDATE research_job_state SET status='INTERRUPTED',claim_id=NULL,lease_until=NULL,
            next_due=?,interrupted=interrupted+1,error_code='LEASE_EXPIRED'
            WHERE status='RUNNING' AND lease_until<=?""",(instant,instant))
        if db.execute("SELECT 1 FROM research_job_state WHERE status='RUNNING' LIMIT 1").fetchone():
            return None
        rows=db.execute("""SELECT job FROM research_job_state WHERE next_due<=?
                           ORDER BY next_due,priority,job""",(instant,)).fetchall()
        job=next((r["job"] for r in rows if r["job"] in jobs),None)
        if job is None:
            return None
        token=uuid4().hex
        db.execute("""UPDATE research_job_state SET status='RUNNING',attempted_at=?,lease_until=?,
                      claim_id=?,error_code=NULL WHERE job=?""",(instant,instant+LEASE_SECONDS,token,job))
        return job,token


def finish(connect,job,token,instant,interval,status):
    if status not in ("PASS_COMPLETED","FAILED","WAITING_EVIDENCE","DISABLED_OR_NOT_AUTHORIZED"):
        raise ValueError("INVALID_JOB_STATUS")
    with closing(connect()) as db,db:
        _table(db)
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT failures FROM research_job_state WHERE job=? AND status='RUNNING' AND claim_id=?",
                       (job,token)).fetchone()
        if row is None:
            return False
        failures=row["failures"]+1 if status=="FAILED" else 0
        # Failure never triggers a busy loop; cap backoff at the normal cadence.
        delay=min(interval,60*2**min(failures-1,8)) if failures else interval
        if status=="WAITING_EVIDENCE" and (job.startswith("GLOBAL_") or job.startswith("RELEASE_") or job=="ECONOMIC_CALENDAR"):
            delay=min(interval,900)
        elif status=="WAITING_EVIDENCE" and job in ("COMPANY_EVIDENCE","FUND_COMPANY_EVIDENCE","INVESTMENT_ANALYST_AI"):
            # A truthful no-evidence outcome must not inadvertently increase
            # the existing provider request budget.
            delay=interval
        elif status=="WAITING_EVIDENCE":
            # Semiannual AMFI publication can lag the period boundary. Avoid
            # minute-by-minute download retries while retaining waiting status.
            delay=min(interval,21600 if job=="AMFI_EQUITY_CAP" else 3600 if job in ("NSE_SURVEILLANCE","NSE_PLEDGE_FILINGS","NSE_FINANCIAL_FILINGS","OFFICIAL_TRI_DOWNLOAD","OFFICIAL_AMC_FACTSHEETS","OFFICIAL_AMFI_TER","FUND_DISCLOSURES","FUND_PORTFOLIOS") else 60)
        db.execute("""UPDATE research_job_state SET status=?,next_due=?,finished_at=?,
            last_completed_at=CASE WHEN ?='PASS_COMPLETED' THEN ? ELSE last_completed_at END,
            claim_id=NULL,lease_until=NULL,failures=?,error_code=?
            WHERE job=? AND claim_id=?""",
            (status,instant+delay,instant,status,instant,failures,
             "RESEARCH_JOB_FAILED" if status=="FAILED" else None,job,token))
        return True


def _stamp(value):
    return datetime.fromtimestamp(value,timezone.utc).isoformat() if value is not None else None


def status(connect,jobs,instant):
    with closing(connect()) as db:
        _table(db)
        indexed={r["job"]:r for r in db.execute("SELECT * FROM research_job_state")}
    items=[]
    for job in jobs:
        row=indexed.get(job)
        state=row["status"] if row else "PENDING"
        if state=="RUNNING" and row["lease_until"]<=instant:
            state="INTERRUPTED"
        items.append({"job":job,"status":state,
            "attempted_at":_stamp(row["attempted_at"]) if row else None,
            "last_completed_at":_stamp(row["last_completed_at"]) if row else None,
            "next_due_at":_stamp(row["next_due"]) if row and row["next_due"]>0 and state!="RUNNING" else None,
            "consecutive_failures":row["failures"] if row else 0,
            "interrupted_attempts":row["interrupted"] if row else 0,
            "error_code":"LEASE_EXPIRED" if state=="INTERRUPTED" else row["error_code"] if row else None})
    return {"status":"PERSISTED_LOCAL_JOB_LEDGER","jobs":items,
            "notice":"PASS_COMPLETED means the scheduled function returned, not that a provider supplied evidence. Source readiness and provider-specific states remain authoritative. Expired claims are retried; one local worker is supported."}
