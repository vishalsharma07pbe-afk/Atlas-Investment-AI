"""Official local Sign in with ChatGPT (not a Codex or browser token importer).

Single operator-owned registration, isolated volume, no HTTP auth API exposed by
ATLAS. OAuth callbacks are available only during the explicitly launched CLI.
"""
import base64
from contextlib import contextmanager
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import time
from urllib.parse import urlencode, urlsplit, parse_qs
import uuid
import httpx

ISSUER="https://auth.openai.com"
RESOURCE="https://api.openai.com/v1"
TOKEN=ISSUER+"/api/accounts/oauth/token"
AUTHORIZE=ISSUER+"/api/accounts/authorize"
JWKS=ISSUER+"/.well-known/jwks.json"
REDIRECT="http://127.0.0.1:1455/auth/callback"
SCOPE="openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
REQUIRED={"resource.invoke","chatgpt.tokens.use.direct"}
CLIENT=re.compile(r"oaiapp_[A-Za-z0-9_-]{1,200}")
MODEL=re.compile(r"[A-Za-z0-9._:/-]{2,100}")
class PlanError(Exception):pass

def directory():
    p=Path(os.getenv("ATLAS_CHATGPT_PLAN_DIR",str(Path.home()/".config/atlas/chatgpt-plan")))
    p.mkdir(mode=0o700,parents=True,exist_ok=True)
    if p.is_symlink() or not p.is_dir():raise PlanError("INVALID_CREDENTIAL_DIRECTORY")
    os.chmod(p,0o700)
    return p

@contextmanager
def locked(blocking=True):
    p=directory()
    fd=os.open(p/"session.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"r+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|(0 if blocking else fcntl.LOCK_NB))
        yield p

def read(p,name):
    try:
        fd=os.open(p/name,os.O_RDONLY|os.O_NOFOLLOW)
    except FileNotFoundError:return {}
    with os.fdopen(fd,"rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode) or os.fstat(f.fileno()).st_mode&0o077:raise PlanError("UNSAFE_CREDENTIAL_PERMISSIONS")
        v=json.loads(f.read(262144))
        if not isinstance(v,dict):raise PlanError("INVALID_CREDENTIAL_RECORD")
        return v

def save(p,name,v):
    fd,path=tempfile.mkstemp(dir=p,prefix=".session-")
    try:
        with os.fdopen(fd,"w") as f:
            os.fchmod(f.fileno(),0o600);json.dump(v,f,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(path,p/name)
    finally:
        if os.path.exists(path):os.unlink(path)

def client():
    return httpx.Client(timeout=httpx.Timeout(45,connect=10),follow_redirects=False,trust_env=False)

def error_code(status,body):
    e=body.get("error",{}) if isinstance(body,dict) else {}
    code=e.get("code") if isinstance(e,dict) else e
    if code in ("subscription_sharing_usage_limit_exceeded","subscription_sharing_usage_unavailable") or status==429:return "PLAN_USAGE_LIMIT"
    if status in (401,403) or code=="invalid_grant":return "PLAN_REAUTH_REQUIRED"
    return "PLAN_REQUEST_FAILED"

def request_json(method,url,**kwargs):
    try:
        with client() as c:
            r=c.request(method,url,**kwargs)
            if len(r.content)>1048576:raise PlanError("PLAN_RESPONSE_TOO_LARGE")
            b=r.json()
            if r.status_code!=200:raise PlanError(error_code(r.status_code,b))
            if not isinstance(b,dict):raise PlanError("INVALID_PLAN_RESPONSE")
            return b
    except (httpx.HTTPError,ValueError):raise PlanError("PLAN_REQUEST_FAILED") from None

def token_request(data):
    return request_json("POST",TOKEN,data={**data,"resource":RESOURCE})

def verify_identity(token,issued,nonce):
    import jwt
    try:
        header=jwt.get_unverified_header(token)
        if header.get("alg")!="RS256":raise PlanError("INVALID_ID_TOKEN")
        keys=request_json("GET",JWKS).get("keys",[])
        selected=[k for k in keys if k.get("kid")==header.get("kid") and k.get("kty")=="RSA"]
        if len(selected)!=1:raise PlanError("INVALID_ID_TOKEN")
        key=jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(selected[0]))
        claims=jwt.decode(token,key,algorithms=["RS256"],audience=issued,issuer=ISSUER,
            options={"require":["exp","iss","aud","sub","nonce"]})
        if not isinstance(claims["sub"],str) or not claims["sub"] or claims["nonce"]!=nonce:raise PlanError("INVALID_ID_TOKEN")
        return claims["sub"]
    except (jwt.PyJWTError,ValueError,TypeError,KeyError):raise PlanError("INVALID_ID_TOKEN") from None

def token_record(data,prior=None):
    prior=prior or {}
    scopes=data.get("scope")
    granted=set(scopes.split()) if isinstance(scopes,str) else set(prior.get("scopes",[]))
    if not REQUIRED<=granted:raise PlanError("PLAN_PERMISSION_REQUIRED")
    access=data.get("access_token");refresh=data.get("refresh_token",prior.get("refresh_token"))
    expires=data.get("expires_in")
    if not isinstance(access,str) or not access or not isinstance(refresh,str) or not refresh or type(expires) is not int or not 0<expires<=86400 or str(data.get("token_type","")).lower()!="bearer":
        raise PlanError("INVALID_TOKEN_RESPONSE")
    return {**prior,"access_token":access,"refresh_token":refresh,"scopes":sorted(granted),"expires_at":time.time()+expires}

def configuration_status():
    # User must disable additional-credit usage in ChatGPT settings first.
    if os.getenv("ATLAS_CHATGPT_PLAN_INCLUDED_ONLY_CONFIRMED","false").lower()!="true":return "PLAN_USAGE_CONFIRMATION_REQUIRED"
    try:
        with locked(blocking=False) as p:
            s=read(p,"session.json")
            if not REQUIRED<=set(s.get("scopes",[])) or not CLIENT.fullmatch(str(s.get("client_id",""))) or not s.get("refresh_token"):return "CHATGPT_SIGN_IN_REQUIRED"
            if not MODEL.fullmatch(str(s.get("model",""))):return "CHATGPT_MODEL_REQUIRED"
            if s.get("reauth_required"):return "CHATGPT_SIGN_IN_REQUIRED"
            if float(s.get("cooldown_until",0))>time.time():return "PLAN_COOLDOWN"
            return "READY_TO_CALL"
    except BlockingIOError:return "PLAN_SESSION_BUSY"
    except (OSError,ValueError,TypeError,PlanError):return "CHATGPT_SIGN_IN_REQUIRED"

def session(p):
    s=read(p,"session.json")
    if not REQUIRED<=set(s.get("scopes",[])) or not CLIENT.fullmatch(str(s.get("client_id",""))) or s.get("reauth_required"):raise PlanError("PLAN_REAUTH_REQUIRED")
    if float(s.get("cooldown_until",0))>time.time():raise PlanError("PLAN_USAGE_LIMIT")
    if float(s.get("expires_at",0))<=time.time()+120:
        try:
            data=token_request({"grant_type":"refresh_token","client_id":s["client_id"],"refresh_token":s["refresh_token"]})
            s=token_record(data,s)
            save(p,"session.json",s)
        except PlanError as e:
            if str(e)=="PLAN_REAUTH_REQUIRED":s["reauth_required"]=True;save(p,"session.json",s)
            raise
    return s

def models(s):
    data=request_json("GET",RESOURCE+"/models",headers={"Authorization":"Bearer "+s["access_token"]})
    return [v["slug"] for v in data.get("models",[]) if isinstance(v,dict) and v.get("visibility")=="list"
        and isinstance(v.get("slug"),str) and MODEL.fullmatch(v["slug"])][:100]

def parse_stream(lines):
    result=[];size=0;total=0;completed=False
    for line in lines:
        total+=len(line)
        if total>2097152:raise PlanError("PLAN_RESPONSE_TOO_LARGE")
        if not line.startswith("data:"):continue
        content=line[5:].strip()
        if content=="[DONE]":break
        try:e=json.loads(content)
        except ValueError:raise PlanError("INVALID_PLAN_STREAM") from None
        if e.get("type")=="response.output_text.delta":
            delta=e.get("delta")
            if not isinstance(delta,str):raise PlanError("INVALID_PLAN_STREAM")
            size+=len(delta)
            if size>16000:raise PlanError("PLAN_RESPONSE_TOO_LARGE")
            result.append(delta)
        elif e.get("type") in ("response.failed","error"):
            raise PlanError(error_code(0,e.get("response",e)))
        elif e.get("type")=="response.incomplete":raise PlanError("PLAN_INCOMPLETE")
        elif e.get("type")=="response.completed":
            completed=True;break
    if not completed or not "".join(result).strip():raise PlanError("PLAN_INCOMPLETE")
    return "".join(result).strip()

def generate(prompt,schema,schema_name):
    if configuration_status()!="READY_TO_CALL":raise PlanError("PLAN_NOT_READY")
    with locked() as p:
        s=session(p)
        try:
            # The preview rejects max_output_tokens and non-streaming requests.
            payload={"model":s["model"],"input":[{"role":"user","content":prompt}],
                     "store":False,"stream":True,"text":{"format":{"type":"json_schema","name":schema_name,"strict":True,"schema":schema}}}
            with client() as c,c.stream("POST",RESOURCE+"/responses",json=payload,
                    headers={"Authorization":"Bearer "+s["access_token"],"Accept":"text/event-stream"}) as r:
                if r.status_code!=200:
                    raise PlanError(error_code(r.status_code,{}))
                return parse_stream(r.iter_lines())
        except PlanError as e:
            if str(e)=="PLAN_USAGE_LIMIT":
                s["cooldown_until"]=time.time()+18000;save(p,"session.json",s)
            if str(e)=="PLAN_REAUTH_REQUIRED":
                s["reauth_required"]=True;save(p,"session.json",s)
            raise
        except (httpx.HTTPError,ValueError,TypeError):raise PlanError("PLAN_REQUEST_FAILED") from None

def connect():
    # Explicit CLI on this local Docker host. No token appears in the browser
    # URL or application logs. The printed URL contains only ephemeral OAuth data.
    with locked() as p:
        previous=read(p,"session.json")
        host=read(p,"host.json")
        if not host.get("id"):
            host={"id":"urn:uuid:"+str(uuid.uuid4())};save(p,"host.json",host)
        issued=previous.get("client_id")
        if issued and not CLIENT.fullmatch(issued):raise PlanError("INVALID_REGISTRATION")
        state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params={"client_id":issued or "dynamic_agent_client","ext_agent_host_id":host["id"],"response_type":"code",
          "redirect_uri":REDIRECT,"scope":SCOPE,"resource":RESOURCE,"state":state,"nonce":nonce,
          "code_challenge_method":"S256","code_challenge":challenge}
        if not issued:params["agent_name_hint"]="ATLAS"
        callback={}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                path=urlsplit(self.path);q=parse_qs(path.query)
                valid=(path.path=="/auth/callback" and len(q.get("state",[]))==1 and secrets.compare_digest(q["state"][0],state))
                if valid:
                    callback.update({k:v[0] for k,v in q.items() if len(v)==1})
                self.send_response(200 if valid else 400)
                self.send_header("Content-Type","text/plain")
                self.send_header("Cache-Control","no-store")
                self.send_header("Referrer-Policy","no-referrer")
                self.end_headers()
                self.wfile.write(b"Return to the ATLAS terminal to finish." if valid else b"Invalid callback.")
        with HTTPServer(("0.0.0.0",1455),Handler) as server:
            server.timeout=1
            print("Open this authorization URL locally (do not share it):",flush=True)
            print(AUTHORIZE+"?"+urlencode(params),flush=True)
            deadline=time.monotonic()+300
            while not callback and time.monotonic()<deadline:server.handle_request()
        if callback.get("error") or not callback.get("code"):raise PlanError("SIGN_IN_CANCELLED_OR_EXPIRED")
        actual=callback.get("client_id") or issued
        if not isinstance(actual,str) or not CLIENT.fullmatch(actual) or (issued and actual!=issued):raise PlanError("INVALID_REGISTRATION")
        data=token_request({"grant_type":"authorization_code","client_id":actual,"code":callback["code"],"code_verifier":verifier,"redirect_uri":REDIRECT})
        subject=verify_identity(data.get("id_token",""),actual,nonce)
        if previous.get("subject") and previous["subject"]!=subject:raise PlanError("ACCOUNT_MISMATCH")
        s=token_record(data,{"client_id":actual,"subject":subject})
        # Save registration even when the model catalog is temporarily unavailable.
        save(p,"session.json",s)
        choices=models(s)
        if not choices:raise PlanError("NO_PLAN_MODELS")
        for i,m in enumerate(choices,1):print(str(i)+". "+m)
        chosen=int(input("Select an available model number: "))
        if not 1<=chosen<=len(choices):raise PlanError("INVALID_MODEL_SELECTION")
        s["model"]=choices[chosen-1];save(p,"session.json",s)
        print("ChatGPT plan connected; actual inference still needs verification.")

def disconnect():
    with locked() as p:
        s=read(p,"session.json")
        if not s:return
        # Preserve only the registration mapping; remote access can also be
        # removed in ChatGPT Settings even if local revocation fails.
        confirmed=False
        try:
            discovery=request_json("GET",ISSUER+"/.well-known/openid-configuration")
            endpoint=discovery.get("revocation_endpoint")
            if isinstance(endpoint,str) and urlsplit(endpoint).netloc=="auth.openai.com" and urlsplit(endpoint).scheme=="https" and s.get("refresh_token"):
                with client() as c:
                    r=c.post(endpoint,data={"token":s["refresh_token"],"token_type_hint":"refresh_token","client_id":s["client_id"]})
                    confirmed=r.status_code==200
        except (PlanError,httpx.HTTPError):pass
        save(p,"session.json",{k:s[k] for k in ("client_id","subject") if k in s})
        print("Disconnected locally."+(" Remote revocation confirmed." if confirmed else " Disconnect ATLAS in ChatGPT Settings; remote revocation not confirmed."))

def main():
    import argparse
    parser=argparse.ArgumentParser(description="ATLAS local ChatGPT plan connection")
    parser.add_argument("action",choices=("connect","status","disconnect"))
    args=parser.parse_args()
    try:
        if args.action=="connect":connect()
        elif args.action=="disconnect":disconnect()
        else:print(configuration_status())
        return 0
    except (PlanError,OSError,ValueError,TypeError,KeyError):
        print("Connection action did not complete. Verify local settings and retry; no credential details printed.")
        return 1

if __name__=="__main__":raise SystemExit(main())
