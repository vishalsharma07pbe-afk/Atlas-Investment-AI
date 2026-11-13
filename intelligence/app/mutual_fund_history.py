"""Read-only, source-attributed NAV history ingestion with strict scheme matching."""
import csv
import io
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
from pydantic import BaseModel,Field
from .mutual_fund_nav import FundNavRequest,analyze_nav

class NavHistoryImport(BaseModel):
    scheme_code:str=Field(min_length=1,max_length=12,pattern=r"^[0-9]+$")
    scheme_name:str=Field(min_length=1,max_length=200)
    source_name:str=Field(min_length=1,max_length=120)
    csv_text:str=Field(min_length=1,max_length=500_000)

def import_nav_history(request:NavHistoryImport)->dict:
    """CSV columns: scheme_code,as_of,nav; YYYY-MM-DD dates; exact scheme match."""
    try:
        reader=csv.DictReader(io.StringIO(request.csv_text))
        if reader.fieldnames is None or set(reader.fieldnames)!={"scheme_code","as_of","nav"}:
            raise ValueError("Required columns: scheme_code,as_of,nav")
        points=[]
        previous=None
        for row in reader:
            if len(points)>=4000:raise ValueError("NAV history exceeds 4000 rows")
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed CSV row")
            if row["scheme_code"].strip()!=request.scheme_code:
                raise ValueError("Scheme code mismatch")
            stamp=date.fromisoformat(row["as_of"].strip())
            value=Decimal(row["nav"].strip())
            if not value.is_finite() or value<=0:raise ValueError("Invalid NAV")
            if previous is not None and stamp<=previous:raise ValueError("NAV dates must increase strictly")
            if stamp>date.today():raise ValueError("Future NAV")
            points.append({"as_of":stamp,"nav":float(value)})
            previous=stamp
        if not points:raise ValueError("NAV history is empty")
        history=FundNavRequest(scheme_code=request.scheme_code,scheme_name=request.scheme_name,
                               source_name=request.source_name,navs=points)
        result=analyze_nav(history)
        result["import"]={"rows_accepted":len(points),"format":"CSV","stored":False,
                          "scheme_match":"EXACT","validation":"PASSED"}
        return result
    except (csv.Error,InvalidOperation,OverflowError) as exc:
        raise ValueError("Invalid NAV history CSV") from None
