#!/usr/bin/env python3
"""Reproduce authorized historical baseline results and cross-check a second corpus.

This is deliberately independent of the live app, DB, model providers and cache.
It does not establish independent source origin or certify the ATLAS decision policy.
"""
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"intelligence"))
from app import long_history_validation as l
from app.independent_valuation import bounded_read

VERSION="OFFLINE-HISTORY-CROSSCHECK-1"
NOTICE="Two operator-supplied corpora, same dated universe, terminal events and normalized total-return paths. Distinct bytes do not prove independent source origin. No full-engine backtest, trading, tax or investment certification."

def crosscheck(a,b):
    days,marks,members,terminal,tri,start=a
    d2,m2,u2,t2,tri2,s2=b
    result={"sessions":len(days),"comparison_sessions":len(d2),"matched_session_calendar":days==d2,"matched_test_start":start==s2,
        "membership_discrepancy_sessions":0,"terminal_discrepancy_sessions":0,"observation_discrepancy_sessions":0,
        "normalized_mark_discrepancies":0,"turnover_discrepancies":0,"tri_discrepancy_sessions":0,"paired_marks":0}
    if days!=d2 or start!=s2:return result
    anchors={}
    for i,day in enumerate(days):
        if set(members[i])!=set(u2[i]):result["membership_discrepancy_sessions"]+=1
        if terminal[i]!=t2[i]:result["terminal_discrepancy_sessions"]+=1
        if set(marks[i])!=set(m2[i]):result["observation_discrepancy_sessions"]+=1
        # Same normalized TRI path, allowing different index bases.
        if abs(tri[i]/tri[0]/(tri2[i]/tri2[0])-1)>.001:result["tri_discrepancy_sessions"]+=1
        for k in set(marks[i])&set(m2[i]):
            a1,av=marks[i][k];b1,bv=m2[i][k]
            result["paired_marks"]+=1
            if k not in anchors and a1>0 and b1>0:anchors[k]=(a1,b1)
            if a1==0 or b1==0:
                if a1!=b1:result["normalized_mark_discrepancies"]+=1
            elif k not in anchors or abs((a1/anchors[k][0])/(b1/anchors[k][1])-1)>.001:
                result["normalized_mark_discrepancies"]+=1
            # Turnover is original observed crore, not reconstructed from
            # adjusted prices. Fixed illustrative tolerance: 1% or 0.1 crore.
            if abs(av-bv)>max(.1,.01*max(av,bv)):result["turnover_discrepancies"]+=1
    return result

def verify(primary,comparison,today):
    raw=bounded_read(primary,l.MAX_BYTES);other=bounded_read(comparison,l.MAX_BYTES)
    h1,h2=sha256(raw).hexdigest(),sha256(other).hexdigest()
    a,b=json.loads(raw),json.loads(other)
    parsed,parsed2=l.parse(a,today),l.parse(b,today)
    checks=crosscheck(parsed,parsed2)
    matched=(h1!=h2 and a["benchmark"]==b["benchmark"] and checks["matched_session_calendar"] and checks["matched_test_start"]
             and checks["paired_marks"]>0 and not any(v for k,v in checks.items() if "discrepanc" in k))
    # Recompute both sets, no reuse of cached dashboard values.
    r1=l.replay(a,today);r2=l.replay(b,today)
    return {"methodology":VERSION,"status":"OPERATOR_CORPORA_CROSSCHECK_MATCHED" if matched else "CROSSCHECK_REVIEW_REQUIRED",
        "qualified":False,"source_independence_verified":False,"as_of":today.isoformat(),
        "primary_sha256":h1,"comparison_sha256":h2,"checks":checks,
        "same_benchmark":a["benchmark"]==b["benchmark"],"distinct_file_digests":h1!=h2,
        "normalized_mark_relative_tolerance":.001,"turnover_relative_tolerance":.01,"turnover_absolute_tolerance_cr":.1,
        "primary_replay":r1,"comparison_replay":r2,"notice":NOTICE}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary",required=True,type=Path);p.add_argument("--comparison",required=True,type=Path)
    p.add_argument("--as-of",required=True,type=date.fromisoformat)
    args=p.parse_args()
    if not l.permitted():
        print(json.dumps({"methodology":VERSION,"status":"DISABLED_OR_NOT_AUTHORIZED","qualified":False}));return 2
    if args.as_of>date.today():
        print(json.dumps({"methodology":VERSION,"status":"FUTURE_AS_OF_REJECTED","qualified":False}));return 2
    try:r=verify(args.primary,args.comparison,args.as_of)
    except (ValueError,TypeError,KeyError,AttributeError,OSError,ArithmeticError):
        print(json.dumps({"methodology":VERSION,"status":"INVALID_OR_INCOMPLETE_CORPUS","qualified":False}));return 2
    print(json.dumps(r,allow_nan=False,indent=2,sort_keys=True))
    return 0 if r["status"]=="OPERATOR_CORPORA_CROSSCHECK_MATCHED" else 1

if __name__=="__main__":raise SystemExit(main())
