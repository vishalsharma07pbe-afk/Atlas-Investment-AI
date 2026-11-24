#!/usr/bin/env python3
"""Restore a real disposable CI production backup into an isolated container.

This is deliberately not a general-purpose live restore utility. It uses the
existing production backup script, never writes into the source database, and
destroys only the uniquely named recovery container and its anonymous volume.
"""
import argparse
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

def verify_sqlite(archive_path,destination):
    with tarfile.open(archive_path,"r:gz") as archive:
        archive.extractall(destination,filter="data")
    snapshots=destination/"ingestion-data"/"research_snapshots.sqlite3"
    if not snapshots.is_file():
        raise AssertionError("Research snapshot database was not backed up")
    checked=0
    for path in sorted(destination.rglob("*.sqlite3")):
        with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as connection:
            if connection.execute("PRAGMA integrity_check").fetchall()!=[("ok",)]:
                raise AssertionError("Recovered SQLite integrity check failed: "+path.name)
        checked+=1
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
        verify_sqlite(backup/"intelligence-state.tar.gz",directory/"restored-intelligence")
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
