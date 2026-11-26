#!/usr/bin/env python3
"""Restore a real disposable CI production backup into an isolated container.

This is deliberately not a general-purpose live restore utility. It uses the
existing production backup script, writes only a synthetic public alert into
the disposable CI intelligence database, never writes into source PostgreSQL,
and destroys only the uniquely named recovery container and its anonymous volume.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
SOURCE="atlas-ci-production"
COMPOSE=["docker","compose","-p",SOURCE,"-f","docker-compose.production.yml"]
COUNTS="""SELECT 'users',count(*) FROM atlas_users
UNION ALL SELECT 'holdings',count(*) FROM personal_holdings
UNION ALL SELECT 'smoke_holdings',count(*) FROM personal_holdings WHERE symbol='CI_PROD'
UNION ALL SELECT 'review_snapshots',count(*) FROM portfolio_review_snapshots
UNION ALL SELECT 'instruments',count(*) FROM instruments
UNION ALL SELECT 'candles',count(*) FROM market_candles
UNION ALL SELECT 'navs',count(*) FROM mutual_fund_nav
UNION ALL SELECT 'migrations',count(*) FROM flyway_schema_history WHERE success
ORDER BY 1;"""

def command(args, **kwargs):
    return subprocess.run(args,cwd=ROOT,check=True,**kwargs)

def output(args):
    return command(args,stdout=subprocess.PIPE,text=True).stdout.strip()

def sql(prefix,query):
    return output(prefix+["psql","-X","-v","ON_ERROR_STOP=1","-U","atlas","-d","atlas","-At","-c",query])

# This probe runs only inside the explicitly guarded disposable production
# stack, using the same app code and volume as the real scheduler.
SEED_ALERT = """
import json
from datetime import datetime, timedelta, timezone
from contextlib import closing
from app import autonomous_research, public_alert_history, public_research_alerts
instant=datetime.now(timezone.utc)
today=instant.astimezone(public_research_alerts.IST).date()
day=(today-timedelta(days=1)).isoformat()
snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY",
 "generated_at":instant.isoformat(),"result":{
 "discovery_coverage":{"calendar_status":"PUBLISHED_SESSION","calendar_checked_on":today.isoformat(),"expected_session":day},
 "price_volume_review":{"downside_items":[{"exchange":"NSE","id":2147483001,"symbol":"CI_RECOVERY",
 "isin":"INE009A01021","as_of":day,"price_volume_pressure":{
 "status":"OBSERVED_PRICE_VOLUME_ONLY","as_of":day,"adjustment_status":"ADJUSTED",
 "calendar_status":"LATEST_SESSION_MATCHED_ONLY","relative_volume":3,"change_percent":-4,
 "findings":["HIGH_VOLUME_DECLINE_REVIEW"]}}]}}}]}
rows=public_research_alerts.market_alerts(snapshot,instant)
assert len(rows)==1
public_alert_history.refresh(autonomous_research._connect,snapshot,instant)
with closing(autonomous_research._connect()) as db:
    row=db.execute("SELECT id,first_recorded,payload FROM public_market_alert_history WHERE id=?",(rows[0]["id"],)).fetchone()
    assert row is not None
    print(json.dumps(dict(row),sort_keys=True))
"""

def verify_research_state(snapshots,expected_alert):
    """Check logical content, not merely file presence or SQLite integrity."""
    with closing(sqlite3.connect(snapshots.as_uri()+"?mode=ro",uri=True)) as db:
        db.row_factory=sqlite3.Row
        row=db.execute("SELECT id,first_recorded,payload FROM public_market_alert_history WHERE id=?",
                       (expected_alert["id"],)).fetchone()
        if row is None or dict(row)!=expected_alert:
            raise AssertionError("Recovered public alert identity, timestamp or payload differs")
        payload=json.loads(row["payload"])
        if (payload.get("id")!=row["id"] or payload.get("category")!="RISK_WARNING"
                or payload.get("source_url") is not None or not payload.get("event_date")):
            raise AssertionError("Recovered public alert provenance invalid")
        jobs=db.execute("SELECT job,status FROM research_job_state WHERE job='PUBLIC_RESEARCH_ALERTS'").fetchall()
        if len(jobs)!=1 or jobs[0]["status"] not in (
            "PENDING","RUNNING","PASS_COMPLETED","FAILED","WAITING_EVIDENCE","INTERRUPTED","DISABLED_OR_NOT_AUTHORIZED"):
            raise AssertionError("Recovered public alert scheduler state missing or invalid")
    print("PASS: recovered exact public alert record and registered scheduler state")

def verify_sqlite(archive_path,destination,expected_alert):
    with tarfile.open(archive_path,"r:gz") as archive:
        archive.extractall(destination,filter="data")
    snapshots=destination/"ingestion-data"/"research_snapshots.sqlite3"
    if not snapshots.is_file():
        raise AssertionError("Research snapshot database was not backed up")
    checked=0
    for path in sorted(destination.rglob("*.sqlite3")):
        with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchall()!=[("ok",)]:
                raise AssertionError("Recovered SQLite integrity check failed: "+path.name)
        checked+=1
    verify_research_state(snapshots,expected_alert)
    print(f"PASS: recovered {checked} SQLite database(s) into isolated temporary storage")

def run():
    if os.environ.get("GITHUB_ACTIONS")!="true" or os.environ.get("COMPOSE_PROJECT_NAME")!=SOURCE:
        raise RuntimeError("DISPOSABLE_CI_ONLY")
    if os.environ.get("POSTGRES_DB")!="atlas" or os.environ.get("POSTGRES_USER")!="atlas":
        raise RuntimeError("UNEXPECTED_CI_DATABASE")
    source_id=output(COMPOSE+["ps","-q","postgres"])
    if not source_id:
        raise RuntimeError("SOURCE_POSTGRES_NOT_RUNNING")
    image=output(["docker","inspect","--format","{{.Image}}",source_id])
    source=COMPOSE+["exec","-T","postgres"]
    expected=sql(source,COUNTS)
    if "smoke_holdings|1" not in expected.splitlines():
        raise AssertionError("Expected disposable production smoke holding missing")
    # The guard above is mandatory. Never seed operator or live deployments.
    expected_alert=json.loads(output(COMPOSE+["exec","-T","intelligence","python","-c",SEED_ALERT]))
    name="atlas-ci-recovery-"+uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="atlas-ci-recovery-") as temporary:
        directory=Path(temporary)
        env=dict(os.environ,ATLAS_BACKUP_DIR=str(directory),ATLAS_PRODUCTION_COMPOSE_FILE=str(ROOT/"docker-compose.production.yml"))
        command(["bash","scripts/backup-production.sh"],env=env)
        backups=[p for p in directory.iterdir() if p.is_dir() and (p/"SHA256SUMS").is_file()]
        if len(backups)!=1:
            raise AssertionError("Expected exactly one verified backup")
        backup=backups[0]
        command(["python3","scripts/verify-production-backup.py",str(backup)])
        verify_sqlite(backup/"intelligence-state.tar.gz",directory/"restored-intelligence",expected_alert)
        try:
            command(["docker","run","-d","--name",name,"--network","none",
                     "-e","POSTGRES_PASSWORD","-e","POSTGRES_USER","-e","POSTGRES_DB",image])
            target=["docker","exec","-i",name]
            deadline=time.monotonic()+90
            while True:
                ready=subprocess.run(target+["pg_isready","-U","atlas","-d","atlas"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                if ready.returncode==0:
                    # The entrypoint initially starts a temporary socket-only server.
                    # A TCP readiness check ensures the final server has started.
                    ready=subprocess.run(target+["pg_isready","-h","127.0.0.1","-U","atlas","-d","atlas"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    if ready.returncode==0:break
                if time.monotonic()>deadline:raise RuntimeError("RECOVERY_DATABASE_START_TIMEOUT")
                time.sleep(2)
            sql(target,"CREATE EXTENSION IF NOT EXISTS timescaledb; SELECT timescaledb_pre_restore();")
            with (backup/"postgres.dump").open("rb") as dump:
                command(target+["pg_restore","--exit-on-error","-U","atlas","-d","atlas"],stdin=dump)
            sql(target,"SELECT timescaledb_post_restore();")
            actual=sql(target,COUNTS)
            if actual!=expected:
                raise AssertionError("Recovered database row counts differ from source")
            # Verify the exact saved holding and its owner, not merely total counts.
            holding_sql="""SELECT h.symbol,h.quantity,h.average_cost,h.last_price,u.email
              FROM personal_holdings h JOIN atlas_users u ON u.id=h.user_id
              WHERE h.symbol='CI_PROD' ORDER BY h.id;"""
            if sql(target,holding_sql)!=sql(source,holding_sql):
                raise AssertionError("Recovered holding or ownership differs")
            print("PASS: isolated TimescaleDB restore, Flyway state, holding values and ownership")
        finally:
            subprocess.run(["docker","rm","-fv",name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print("PASS: disposable production recovery drill")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable-ci-stack",action="store_true",required=True)
    parser.parse_args()
    run()
