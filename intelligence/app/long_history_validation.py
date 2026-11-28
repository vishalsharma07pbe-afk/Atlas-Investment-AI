"""Authorized offline historical-universe comparison, separate from 500-bar replay.

Uses operator-attested dated membership and total-return observations; neither
provenance nor coverage is independently certified. Fixed price-only baselines,
not a historical reconstruction of the entire ATLAS decision engine.
"""
from contextlib import closing
from datetime import date
from hashlib import sha256
from math import isfinite,sqrt
from statistics import mean,median,pstdev
from pathlib import Path
import json,os,stat
from .replay_evidence import exact_isin
from .independent_valuation import bounded_read

VERSION="ATLAS-LONG-HISTORY-1"
PATH=Path("/app/filing-reports/long-history.json")
MAX_BYTES=64_000_000
COST=.003
NOTICE="Operator-attested historical membership, adjusted total-return marks and terminal events. Fixed monthly momentum versus equal-weight eligible universe and gross TRI; next-session closing mark, fractional return-index units, full turnover friction. No point-in-time financial inputs, execution, tax, independent source certification or qualification."

def permitted():
    return os.getenv("ATLAS_LONG_HISTORY_VALIDATION_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def num(x,a,b):return type(x) in (int,float) and isfinite(x) and a<=x<=b

def parse(root,today):
    if root.get("methodology")!=VERSION or not all(root.get(k) is True for k in ("authorization_attested","historical_membership_attested","total_return_and_terminal_events_attested")):raise ValueError("ATTESTATION")
    if root.get("benchmark") not in ("NIFTY 100 TRI","NIFTY MIDCAP 150 TRI","NIFTY SMALLCAP 250 TRI","NIFTY 500 TRI","NIFTY 50 TRI"):raise ValueError("BENCHMARK")
    rows=root.get("sessions")
    if not isinstance(rows,list) or not 1250<=len(rows)<=3000:raise ValueError("SESSION_COUNT")
    days=[];marks=[];members=[];terminal=[];benchmark=[];ended=set()
    for row in rows:
        day=date.fromisoformat(row["date"]);known=date.fromisoformat(row["membership_known_on"])
        if day>=today or known>day or days and not 1<=(day-days[-1]).days<=7:raise ValueError("DATE")
        universe=row["members"];obs=row["observations"];end=row.get("terminal",[])
        if not isinstance(universe,list) or not 10<=len(universe)<=150 or len(set(universe))!=len(universe) or any(not exact_isin(k) or k in ended for k in universe):raise ValueError("MEMBERSHIP")
        if not isinstance(obs,dict) or not len(universe)<=len(obs)<=250 or any(not exact_isin(k) or k in ended for k in obs) or not set(universe)<=set(obs):raise ValueError("OBSERVATIONS")
        if not isinstance(end,list) or len(set(end))!=len(end) or not set(end)<=set(obs) or set(end)&set(universe):raise ValueError("TERMINAL")
        for k,v in obs.items():
            if not isinstance(v,list) or len(v)!=2 or not num(v[0],0 if k in end else .00000001,1e12) or not num(v[1],0,1e12):raise ValueError("MARK")
        if not num(row["benchmark_tri"],.000001,1e12):raise ValueError("TRI")
        ended.update(end);days.append(day);marks.append(obs);members.append(universe);terminal.append(set(end));benchmark.append(row["benchmark_tri"])
    start=next((i for i in range(127,len(days)) if days[i].month!=days[i-1].month),None)
    if start is None or not 1825<=(days[-1]-days[start]).days<=3660:raise ValueError("FIVE_TO_TEN_YEAR_TEST_SPAN")
    return days,marks,members,terminal,benchmark,start

def metrics(path,days):
    if len(path)!=len(days) or any(not num(x,0,1e15) for x in path) or path[0]<=0:raise ValueError("PORTFOLIO_PATH")
    changes=[b/a-1 for a,b in zip(path,path[1:]) if a>0]
    years=(days[-1]-days[0]).days/365.2425
    peak=path[0];drawdown=0
    for value in path:
        peak=max(peak,value);drawdown=min(drawdown,value/peak-1)
    sd=pstdev(changes) if changes else 0
    downside=sqrt(mean([min(0,x)**2 for x in changes])) if changes else 0
    return {"total_return_percent":round(100*(path[-1]/path[0]-1),4),"cagr_percent":round(100*((path[-1]/path[0])**(1/years)-1),4),
        "max_drawdown_percent":round(100*drawdown,4),"annualized_sharpe_rf_zero":round(mean(changes)/sd*sqrt(252),4) if sd else None,
        "annualized_sortino_rf_zero":round(mean(changes)/downside*sqrt(252),4) if downside else None}

def replay(root,today):
    days,marks,members,terminal,benchmark,start=parse(root,today)
    cash=[1.,1.];held=[{},{}];paths=[[1.],[1.]];turnover=[0,0];rebalance=0;candidate_counts=[]
    for i in range(start,len(days)):
        current=marks[i]
        for j in range(2):
            for k in list(held[j]):
                if k not in current:raise ValueError("MISSING_HELD_MARK_OR_TERMINAL_EVENT")
                if k in terminal[i]:cash[j]+=held[j].pop(k)*current[k][0]
        if days[i].month!=days[i-1].month:
            # Prior session membership and 126 earlier sessions. Exclude
            # latest 21 sessions; require contiguous history, no IPO imputation.
            prev=i-1;eligible=[]
            for k in members[prev]:
                window=marks[prev-126:prev+1]
                if any(k not in r or r[k][0]<=0 for r in window):continue
                if median(r[k][1] for r in window[-20:])<5:continue
                momentum=window[-22][k][0]/window[0][k][0]-1
                eligible.append((momentum,k))
            if len(eligible)<10:raise ValueError("INSUFFICIENT_CAUSAL_ELIGIBLE_UNIVERSE")
            eligible.sort(key=lambda x:(-x[0],x[1]));candidate_counts.append(len(eligible));rebalance+=1
            for j,selection in enumerate((eligible[:10],eligible)):
                # Close-confirmed signal is executed at following session's
                # closing return-index mark, not same-session close.
                for k,units in held[j].items():
                    proceeds=units*current[k][0];cash[j]+=proceeds*(1-COST);turnover[j]+=1
                held[j]={}
                amount=cash[j]/len(selection)/(1+COST)
                for _,k in selection:
                    if k not in current or current[k][0]<=0 or k in terminal[i]:raise ValueError("MISSING_NEXT_SESSION_ENTRY_MARK")
                    held[j][k]=amount/current[k][0];cash[j]-=amount*(1+COST);turnover[j]+=1
                cash[j]=max(0,cash[j])
        for j in range(2):paths[j].append(cash[j]+sum(units*current[k][0] for k,units in held[j].items()))
    # First daily observation is before the first rebalance cost; label
    # baseline date as first execution session, not training end.
    dates=[days[start],*days[start:]]
    # Duplicate initial date is only the initial wealth at the first mark.
    index=[1.,*[v/benchmark[start] for v in benchmark[start:]]]
    result={"methodology":VERSION,"status":"OPERATOR_ATTESTED_BASELINE_COMPARISON","qualified":False,"start":days[start].isoformat(),"end":days[-1].isoformat(),
        "sessions":len(days)-start,"monthly_rebalances":rebalance,"min_eligible_companies":min(candidate_counts),"terminal_events_in_corpus":sum(map(len,terminal)),"cost_bps_per_side":30,"benchmark":root["benchmark"],
        "momentum_top10":metrics(paths[0],dates),"equal_weight_eligible":metrics(paths[1],dates),"benchmark_tri":metrics(index,dates),
        "trade_mark_events":{"momentum":turnover[0],"equal_weight":turnover[1]},"notice":NOTICE}
    # Predeclared chronological halves, with original portfolio path carried
    # forward. No parameter fitting or choosing the best period.
    cut=len(dates)//2
    result["chronological_windows"]=[{"start":dates[a].isoformat(),"end":dates[b-1].isoformat(),"momentum":metrics(paths[0][a:b],dates[a:b]),"equal_weight":metrics(paths[1][a:b],dates[a:b]),"benchmark":metrics(index[a:b],dates[a:b])} for a,b in ((0,cut+1),(cut,len(dates)))]
    return result

def _file_key(path):
    x=path.stat(follow_symlinks=False)
    if not stat.S_ISREG(x.st_mode) or not 0<x.st_size<=MAX_BYTES:raise ValueError("FILE")
    return f"{x.st_ino}:{x.st_size}:{x.st_mtime_ns}:{x.st_ctime_ns}"

def _table(db):
    db.execute("CREATE TABLE IF NOT EXISTS atlas_long_history_validation (id INTEGER PRIMARY KEY CHECK(id=1), file_key TEXT NOT NULL, payload TEXT NOT NULL)")

def read(connect,path=PATH):
    out={"methodology":VERSION,"status":"DISABLED_OR_NOT_AUTHORIZED","qualified":False,"notice":NOTICE}
    if not permitted():return out
    out["status"]="AWAITING_AUTHORIZED_LONG_HISTORY"
    try:
        key=_file_key(path)
        with closing(connect()) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='atlas_long_history_validation'").fetchone():return out
            row=db.execute("SELECT payload FROM atlas_long_history_validation WHERE id=1 AND file_key=?",(key,)).fetchone()
        if row:
            result=json.loads(row[0])
            if result.get("methodology")==VERSION and result.get("qualified") is False:return result
    except (OSError,ValueError,TypeError,KeyError):pass
    return out

def refresh(connect,instant,path=PATH):
    if not permitted():return False
    try:
        key=_file_key(path)
        existing=read(connect,path)
        if existing.get("status")!="AWAITING_AUTHORIZED_LONG_HISTORY":return existing.get("status")=="OPERATOR_ATTESTED_BASELINE_COMPARISON"
        raw=bounded_read(path,MAX_BYTES)
        if _file_key(path)!=key:return False
        from zoneinfo import ZoneInfo
        result=replay(json.loads(raw),instant.astimezone(ZoneInfo("Asia/Kolkata")).date())
        result["corpus_sha256"]=sha256(raw).hexdigest()
    except (OSError,ValueError,TypeError,KeyError,AttributeError,ArithmeticError):return False
    with closing(connect()) as db,db:
        _table(db)
        db.execute("INSERT INTO atlas_long_history_validation VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET file_key=excluded.file_key,payload=excluded.payload",(key,json.dumps(result,allow_nan=False)))
    return True
