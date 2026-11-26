"""Resolve the current note owner using the existing Spring session authority."""
import json
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from uuid import UUID
from fastapi import HTTPException

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def session_authorization(request):
    authorization=request.headers.get("authorization","")
    cookie=request.cookies.get("ATLAS_SESSION")
    if not authorization.startswith("Bearer ") and cookie:
        authorization="Bearer "+cookie
    if not authorization.startswith("Bearer ") or not 1<=len(authorization[7:])<=4096:
        raise HTTPException(401,"Authentication required")
    # Cookie writes must originate from the same dashboard. Fetch metadata is
    # browser-controlled; a same-origin browser behind Vite may have a rewritten Host.
    if cookie and request.method not in ("GET","HEAD","OPTIONS"):
        site=request.headers.get("sec-fetch-site")
        origin=request.headers.get("origin")
        if site is not None and site!="same-origin":
            raise HTTPException(403,"Cross-origin cookie request rejected")
        if site is None and (not origin or urlsplit(origin).netloc.lower()!=request.headers.get("host","").lower()):
            raise HTTPException(403,"Cross-origin cookie request rejected")
    return authorization

def owner_for(request,backend_url):
    authorization=session_authorization(request)
    try:
        opener=build_opener(ProxyHandler({}),_NoRedirect())
        req=Request(backend_url.rstrip("/")+"/api/v1/auth/me",headers={"Accept":"application/json","Authorization":authorization})
        with opener.open(req,timeout=5) as response:
            raw=response.read(8193)
            if len(raw)>8192:
                raise ValueError("Invalid session response")
            data=json.loads(raw)
            return UUID(data["id"])
    except HTTPError as exc:
        if exc.code in (401,403):
            raise HTTPException(401,"Authentication required") from None
        raise HTTPException(503,"Session authority unavailable") from None
    except (URLError,OSError,ValueError,TypeError,KeyError,AttributeError):
        raise HTTPException(503,"Session authority unavailable") from None
