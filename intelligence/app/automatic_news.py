"""Bounded source-linked company event observations, not sentiment or advice."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from ipaddress import ip_address
import json
import os
import re
from urllib.parse import urlsplit, urlunsplit

from .automatic_company_evidence import identify
from .p1_research import company_news

NOTICE = ("Provider headlines only; underlying claims, completeness and market impact are not independently verified. "
          "Headline topic matches are review prompts, not confirmed events or sentiment. No article means no usable returned evidence, not no risk.")
TOPICS = {
    "EARNINGS": r"\b(?:earnings|quarterly results|profit warning|financial results|revenue guidance)\b",
    "REGULATORY": r"\b(?:sebi|regulatory|investigation|penalty|fraud|insolvency|default|recall)\b",
    "CORPORATE_ACTION": r"\b(?:dividend|buyback|stock split|bonus issue|rights issue)\b",
    "TRANSACTION": r"\b(?:merger|acquisition|demerger|stake sale|takeover)\b",
    "MANAGEMENT": r"\b(?:resignation|resigns|chief executive|management change|auditor)\b",
}


def permitted():
    return (os.getenv("ATLAS_AUTOMATIC_NEWS_ENABLED","false").lower()=="true"
            and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"
            and os.getenv("MARKET_DATA_ENTITLEMENT_CONFIRMED","false").lower()=="true"
            and bool(os.getenv("UPSTOX_ACCESS_TOKEN","").strip()))


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_news_state(
        instrument_key TEXT PRIMARY KEY, attempted_at TEXT NOT NULL,
        next_attempt_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT)""")


def _stamp(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_TIMESTAMP")
    result=datetime.fromisoformat(value.replace("Z","+00:00"))
    if result.tzinfo is None:
        raise ValueError("INVALID_TIMESTAMP")
    return result.astimezone(timezone.utc)


def _url(value):
    if not isinstance(value,str) or not 8<=len(value)<=1000 or any(c.isspace() for c in value):
        raise ValueError("INVALID_URL")
    p=urlsplit(value)
    host=(p.hostname or "").lower().rstrip(".")
    if p.scheme!="https" or not host or p.username or p.password or "." not in host or host.endswith((".local",".internal",".localhost")):
        raise ValueError("INVALID_URL")
    try:
        address=ip_address(host)
    except ValueError:
        address=None
    if address is not None and not address.is_global:
        raise ValueError("INVALID_URL")
    # Do not fetch the article or retain tracking/credential query values.
    # Retain public article links as supplied except fragments. Reject likely
    # credential-bearing query keys; do not silently rewrite article identity.
    if re.search(r"(?:^|&)(?:token|access_token|api_key|apikey|password|secret|signature|sig)=",p.query,re.I):
        raise ValueError("INVALID_URL")
    return urlunsplit((p.scheme,p.netloc,p.path,p.query,""))


def normalize(report, keys, instant):
    returned=report.get("returned_keys")
    articles=report.get("articles")
    if not isinstance(returned,list) or not isinstance(articles,list):
        raise ValueError("INVALID_REPORT")
    output={key:{} for key in keys if key in returned}
    for article in articles[:500]:
        try:
            key=article["instrument_key"]
            if key not in output or article.get("source_provider")!="UPSTOX_NEWS":
                continue
            stamp=_stamp(article["published_at"])
            if not timedelta(0)<=instant-stamp<=timedelta(hours=72):
                continue
            url=_url(article["url"])
            headline=article["headline"]
            if not isinstance(headline,str) or not headline.strip() or headline=="Untitled article":
                continue
            headline=" ".join(headline.split())[:300]
            if len(headline)<8:
                continue
            article_id=sha256((url+"\n"+stamp.isoformat()).encode()).hexdigest()[:40]
            topics=[name for name,pattern in TOPICS.items() if re.search(pattern,headline,re.I)]
            output[key].setdefault(article_id,{"id":article_id,"headline":headline,"url":url,
                "published_at":stamp.isoformat(),"topics":topics,"sentiment":"NOT_ANALYZED",
                "source_provider":"UPSTOX_NEWS"})
        except (KeyError,TypeError,ValueError,AttributeError,OverflowError):
            continue
    return {key:sorted(rows.values(),key=lambda row:(row["published_at"],row["id"]),reverse=True)[:10]
            for key,rows in output.items()}


def refresh(snapshot,connect,loader=company_news,instant=None):
    if not snapshot["enabled"] or not permitted():
        return
    instant=instant or datetime.now(timezone.utc)
    stamp=instant.isoformat()
    # Reuse active registry ISIN; BSE key cannot be inferred from ticker/ISIN.
    candidates=sorted({"NSE_EQ|"+isin for item,isin in identify(snapshot) if item["exchange"]=="NSE"})
    if not candidates:
        return
    with closing(connect()) as db,db:
        _table(db)
        db.execute("BEGIN IMMEDIATE")
        rows={r["instrument_key"]:r for r in db.execute("SELECT * FROM automatic_news_state")}
        if any(r["attempted_at"]>(instant-timedelta(minutes=15)).isoformat() for r in rows.values()):
            return
        keys=sorted((k for k in candidates if k not in rows or rows[k]["next_attempt_at"]<=stamp),
                    key=lambda k:(rows[k]["attempted_at"] if k in rows else "",k))[:10]
        if not keys:
            return
        for key in keys:
            db.execute("""INSERT INTO automatic_news_state VALUES(?,?,?,'RUNNING',NULL)
                ON CONFLICT(instrument_key) DO UPDATE SET attempted_at=excluded.attempted_at,
                next_attempt_at=excluded.next_attempt_at,status='RUNNING',payload=NULL""",
                (key,stamp,(instant+timedelta(hours=1)).isoformat()))
    try:
        result=normalize(loader(keys,page_size=20),keys,instant)
    except Exception:
        result={}
    with closing(connect()) as db,db:
        for key in keys:
            status="REVIEW_AVAILABLE" if result.get(key) else "NO_RECENT_RETURNED_ARTICLES" if key in result else "UNAVAILABLE"
            db.execute("""UPDATE automatic_news_state SET status=?,payload=?,next_attempt_at=?
                WHERE instrument_key=? AND attempted_at=?""",
                (status,json.dumps(result[key],allow_nan=False) if key in result else None,
                 (instant+timedelta(minutes=30 if key in result else 60)).isoformat(),key,stamp))
        db.execute("DELETE FROM automatic_news_state WHERE attempted_at<?",((instant-timedelta(days=7)).isoformat(),))


def read(connect,instant=None):
    if not permitted():
        return {}
    instant=instant or datetime.now(timezone.utc)
    output={}
    with closing(connect()) as db:
        _table(db)
        for row in db.execute("SELECT * FROM automatic_news_state WHERE attempted_at BETWEEN ? AND ?",
                ((instant-timedelta(hours=2)).isoformat(),instant.isoformat())):
            status=row["status"]
            articles=[a for a in json.loads(row["payload"] or "[]")
                      if timedelta(0)<=instant-_stamp(a["published_at"])<=timedelta(hours=72)]
            if status=="REVIEW_AVAILABLE" and not articles:
                status="NO_RECENT_RETURNED_ARTICLES"
            output[row["instrument_key"]]={"status":status,"retrieved_at":row["attempted_at"],
                    "articles":articles,"notice":NOTICE}
    return output


def attach(snapshot,connect,instant=None):
    snapshot["automatic_news_status"]="DISABLED_OR_NOT_AUTHORIZED"
    if not snapshot["enabled"] or not permitted():
        return snapshot
    snapshot["automatic_news_status"]="ENABLED"
    by_key=read(connect,instant)
    latest={}
    for item,isin in identify(snapshot):
        if item["exchange"]!="NSE":
            continue
        section=by_key.get("NSE_EQ|"+isin)
        if section:
            item["news_evidence"]=section
            for article in section["articles"]:
                latest.setdefault(article["id"],article)
    snapshot["recent_company_news"]=sorted(latest.values(),key=lambda a:(a["published_at"],a["id"]),reverse=True)[:10]
    return snapshot


def alerts(connect,instant=None):
    """Adapt recent topic-matched observations to existing public bell contract."""
    articles={}
    for section in read(connect,instant).values():
        for article in section["articles"]:
            if article["topics"]:
                articles.setdefault(article["id"],article)
    result=[]
    for article in sorted(articles.values(),key=lambda a:(a["published_at"],a["id"]),reverse=True)[:30]:
        result.append({"id":"company-news-"+article["id"],"category":"MARKET_EVENT",
            "title":article["headline"][:160],"description":"Headline review topics: "+", ".join(article["topics"])+
                ". Provider-reported news, not independently verified; sentiment and market impact unknown.",
            "published_at":article["published_at"],"source_name":"Upstox News","source_url":article["url"]})
    return result
