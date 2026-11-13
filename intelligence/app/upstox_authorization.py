"""Read-only Upstox V3 feed authorization; signed WSS URLs stay server-side."""
import json
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from .upstox_stream import validate_redirect

AUTHORIZE_URL="https://api.upstox.com/v3/feed/market-data-feed/authorize"

class AuthorizationError(RuntimeError):
    """Safe error that never includes credentials or signed URLs."""

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def authorize_feed(token: str, opener=None) -> str:
    """Return validated signed WSS URI to trusted server-side caller only."""
    if not isinstance(token,str) or not token.strip() or "\n" in token or "\r" in token:
        raise AuthorizationError("Provider credential missing or invalid")
    request=Request(AUTHORIZE_URL,headers={
        "Accept":"application/json",
        "Authorization":"Bearer "+token,
    },method="GET")
    try:
        client=opener if opener is not None else build_opener(_NoRedirect())
        with client.open(request,timeout=10) as response:
            if response.status!=200:
                raise AuthorizationError("Provider authorization rejected")
            raw=response.read(65537)
            if len(raw)>65536:
                raise AuthorizationError("Provider authorization response too large")
        payload=json.loads(raw)
        if not isinstance(payload,dict) or payload.get("status")!="success":
            raise AuthorizationError("Provider authorization rejected")
        data=payload.get("data")
        if not isinstance(data,dict) or not isinstance(data.get("authorized_redirect_uri"),str):
            raise AuthorizationError("Provider authorization response invalid")
        try:
            return validate_redirect(data["authorized_redirect_uri"])
        except (ValueError,TypeError) as exc:
            raise AuthorizationError("Provider returned untrusted feed endpoint") from None
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,json.JSONDecodeError) as exc:
        raise AuthorizationError("Provider feed authorization unavailable") from None

def authorization_diagnostics(provider: str, token_present: bool, rights: bool, entitlement: bool) -> dict:
    blockers=[]
    if provider!="UPSTOX":blockers.append("UPSTOX_NOT_SELECTED")
    if not token_present:blockers.append("ACCESS_TOKEN_MISSING")
    if not rights:blockers.append("DATA_USAGE_RIGHTS_UNCONFIRMED")
    if not entitlement:blockers.append("MARKET_DATA_ENTITLEMENT_UNCONFIRMED")
    return {"status":"CONFIGURED" if not blockers else "BLOCKED",
            "authorization_request_performed":False,
            "live_stream_connected":False,
            "blockers":blockers,
            "notice":"Configuration checks only. No live quotes, authorization URL, or credentials are returned."}
