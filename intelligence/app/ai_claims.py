"""Exact scalar assertions over the already sanitized public evidence pack.

No arbitrary model prose, inferred facts, recommendations or raw invalid
values are persisted. Matching the supplied observation is not verifying its
real-world truth, nor agreement about an investment.
"""
import json
from math import isfinite
import re

PATH=re.compile(r"^/(?:[A-Za-z0-9_]+/){0,7}[A-Za-z0-9_]+$")
NOTICE=("Only exact values of supplied observations are checked. Shared matches are not independent corroboration; "
        "conflicts are assertions about the same observation, not general interpretive disagreement. "
        "No investment verdict or calibrated confidence.")

def _catalog(supplied):
    result={}
    def visit(value,path,depth):
        if depth>8 or len(result)>=600:
            return
        if isinstance(value,dict):
            for k,v in value.items():
                if isinstance(k,str) and re.fullmatch(r"[A-Za-z0-9_]+",k):
                    visit(v,path+"/"+k,depth+1)
        elif isinstance(value,list):
            for i,v in enumerate(value[:100]):
                visit(v,path+"/"+str(i),depth+1)
        elif type(value) in (str,int,float,bool) and (type(value) not in (int,float) or isfinite(value)):
            result[path]=value
    for key,value in supplied.items():
        if isinstance(key,str) and re.fullmatch(r"[A-Z]+",key):
            visit(value,"/"+key,1)
    return result

def _object(pairs):
    result={}
    for k,v in pairs:
        if k in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[k]=v
    return result

def _scalar(value):
    return type(value) in (int,float,bool,str) and (type(value) not in (int,float) or isfinite(value))

def _equal(actual,claimed):
    if type(actual) in (int,float) and type(claimed) in (int,float):
        return actual==claimed
    return type(actual) is type(claimed) and actual==claimed

def audit(supplied,findings):
    catalog=_catalog(supplied)
    proposed={}
    rejected=0
    duplicates=0
    for finding in findings[:8]:
        try:
            statement=finding["statement"]
            cited=finding["evidence_ids"]
            if not isinstance(statement,str) or not 1<=len(statement)<=500:
                raise ValueError("INVALID_STATEMENT")
            obj=json.loads(statement,object_pairs_hook=_object)
            if not isinstance(obj,dict) or set(obj)!={"path","value"}:
                raise ValueError("INVALID_CLAIM")
            path,value=obj["path"],obj["value"]
            if (not isinstance(path,str) or not PATH.fullmatch(path) or path not in catalog
                or cited!=[path.split("/")[1]] or not _scalar(value)):
                raise ValueError("UNSUPPORTED_CLAIM")
            proposed.setdefault(path,[]).append(_equal(catalog[path],value))
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
            rejected+=1
    claims=[]
    clean=[]
    for path,checks in sorted(proposed.items()):
        if len(checks)!=1:
            duplicates+=len(checks)
            continue
        status="MATCHED" if checks[0] else "CONTRADICTED"
        claims.append({"path":path,"status":status})
        if checks[0]:
            # Render only the trusted scalar and its exact location. Preserve
            # source scope via domain ID; never reuse the model's statement.
            clean.append({"statement":path+" = "+json.dumps(catalog[path],ensure_ascii=True),
                          "evidence_ids":[path.split("/")[1]],"claim_path":path})
    return {"claims":claims,"findings":clean,"rejected_count":rejected,"duplicate_count":duplicates}

def compare(supplied,reviews):
    catalog=_catalog(supplied)
    indexed={}
    rejected=duplicates=0
    seen=set()
    for review in reviews:
        provider=review.get("provider")
        if provider not in ("OLLAMA","GEMINI","GROQ","OPENAI","XAI") or provider in seen:
            continue
        seen.add(provider)
        block=review.get("claim_audit") or {}
        for key in ("rejected_count","duplicate_count"):
            value=block.get(key,0)
            if type(value) is int and 0<=value<=8:
                if key=="rejected_count":
                    rejected+=value
                else:
                    duplicates+=value
        rows=block.get("claims",[])
        for row in rows[:8]:
            path=row.get("path")
            status=row.get("status")
            if path not in catalog or status not in ("MATCHED","CONTRADICTED"):
                continue
            if sum(r.get("path")==path for r in rows)!=1:
                continue
            indexed.setdefault(path,{"MATCHED":[],"CONTRADICTED":[]})[status].append(provider)
    shared=[]
    conflicts=[]
    matches=wrong=0
    for path,groups in sorted(indexed.items()):
        yes,no=sorted(groups["MATCHED"]),sorted(groups["CONTRADICTED"])
        matches+=len(yes)
        wrong+=len(no)
        if yes and no:
            conflicts.append({"path":path,"matching_providers":yes,"contradicting_providers":no})
        elif len(yes)>=2:
            shared.append({"path":path,"providers":yes})
    status=("CONFLICTING_ASSERTIONS" if conflicts else "CONTRADICTED_ASSERTIONS_PRESENT" if wrong else
            "SHARED_MATCHED_OBSERVATIONS_ONLY" if shared else "NO_SHARED_COMPARABLE_ASSERTIONS" if matches else "NOT_ASSESSED")
    return {"status":status,"matched_count":matches,"contradicted_count":wrong,"rejected_count":rejected,
            "duplicate_count":duplicates,"shared_matches":shared,"conflicts":conflicts,"notice":NOTICE}
