"""Official dated AMFI six-month average cap table, fetched only by scheduler."""
from contextlib import closing
from datetime import date
from io import BytesIO
from math import isfinite
import os
import re
from zipfile import ZipFile
import httpx
from .replay_evidence import exact_isin

# Exact published AMFI workbook verified against the official June 2026 list.
SOURCE_DATE=date(2026,6,30)
URL="https://portal.amfiindia.com/spages/AverageMarketCapitalization30Jun2026.xlsx"
INTERVAL=86400
MAX_BYTES=8_000_000

def permitted():
    return os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def parse(payload):
    from openpyxl import load_workbook
    if len(payload)>MAX_BYTES:
        raise ValueError("AMFI_CAP_SIZE")
    with ZipFile(BytesIO(payload)) as z:
        if len(z.infolist())>100 or sum(i.file_size for i in z.infolist())>40_000_000:
            raise ValueError("AMFI_CAP_EXPANSION")
    book=load_workbook(BytesIO(payload),read_only=True,data_only=True,keep_links=False)
    result={}
    try:
        for sheet in book.worksheets[:5]:
            header=None
            for row in sheet.iter_rows(min_row=1,max_row=10000,max_col=20,values_only=True):
                text=[" ".join(str(v or "").lower().split()) for v in row]
                if header is None:
                    if "isin" in text and any("average of all exchanges" in t for t in text) and any("categorization" in t or "categorisation" in t for t in text):
                        header=(text.index("isin"),next(i for i,t in enumerate(text) if "average of all exchanges" in t),
                                next(i for i,t in enumerate(text) if "categorization" in t or "categorisation" in t))
                    continue
                isin=row[header[0]]
                if not exact_isin(isin):
                    continue
                category=" ".join(str(row[header[2]] or "").upper().split()).replace(" ","_")
                if category not in ("LARGE_CAP","MID_CAP","SMALL_CAP"):
                    continue
                raw=row[header[1]]
                try: value=float(str(raw).replace(",",""))
                except (ValueError,TypeError): continue
                if not isfinite(value) or not 0<value<100_000_000:
                    continue
                if isin in result:
                    raise ValueError("AMFI_DUPLICATE_ISIN")
                result[isin]={"cap_category":category,"average_cap_cr":value,"cap_as_of":SOURCE_DATE.isoformat()}
        if len(result)<250 or sum(v["cap_category"]=="LARGE_CAP" for v in result.values())!=100:
            raise ValueError("AMFI_CAP_COVERAGE")
        return result
    finally:
        book.close()

def refresh(connect,today):
    if not permitted() or not 0<=(today-SOURCE_DATE).days<=220:
        return False
    data=bytearray()
    with httpx.Client(timeout=20,follow_redirects=False) as client:
        with client.stream("GET",URL,headers={"User-Agent":"ATLAS-Research/2.0"}) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data)>MAX_BYTES: raise ValueError("AMFI_CAP_SIZE")
    rows=parse(bytes(data))
    with closing(connect()) as db,db:
        db.execute("CREATE TABLE IF NOT EXISTS amfi_equity_cap(isin TEXT PRIMARY KEY,category TEXT NOT NULL,average_cap_cr REAL NOT NULL,as_of TEXT NOT NULL)")
        db.execute("DELETE FROM amfi_equity_cap")
        db.executemany("INSERT INTO amfi_equity_cap VALUES(?,?,?,?)",[(k,v["cap_category"],v["average_cap_cr"],v["cap_as_of"]) for k,v in rows.items()])
    return True

def read(connect,today):
    if not permitted() or not 0<=(today-SOURCE_DATE).days<=220:
        return {}
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='amfi_equity_cap'").fetchone():
            return {}
        return {r["isin"]:{"cap_category":r["category"],"average_cap_cr":r["average_cap_cr"],"cap_as_of":r["as_of"]}
                for r in db.execute("SELECT * FROM amfi_equity_cap WHERE as_of=?",(SOURCE_DATE.isoformat(),))}
