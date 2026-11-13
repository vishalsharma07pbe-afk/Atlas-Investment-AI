"""Opt-in HTTPS JSON notification adapter for a licensed provider.

Never guesses exchange endpoints or scrapes public pages. Operator configures an
exact provider HTTPS URL and a separately granted bearer token.
"""
import argparse,ipaddress,json,os,socket,ssl,tempfile,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from pydantic import BaseModel,Field,model_validator
from .notification_import import Snapshot,import_snapshot

class ProviderConfig(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    endpoint:str=Field(pattern=r"^https://",max_length=1000)
    token_env:str=Field(pattern=r"^ATLAS_PROVIDER_[A-Z0-9_]{3,64}$")
    collection_authorized:bool=False
    redistribution_authorized:bool=False
    enabled:bool=False

    @model_validator(mode="after")
    def check(self):
        parsed=urllib.parse.urlsplit(self.endpoint)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("A plain HTTPS endpoint without credentials or fragment is required")
        if parsed.port not in (None,443):raise ValueError("Only HTTPS port 443 is supported")
        if parsed.hostname.lower() in ("localhost","localhost.localdomain") or parsed.hostname.lower().endswith(".local"):
            raise ValueError("Local provider endpoints are forbidden")
        if self.enabled and not(self.collection_authorized and self.redistribution_authorized):
            raise ValueError("Enabled provider requires declared collection and redistribution permissions")
        return self

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError("Provider redirects are forbidden")

def _public_host(hostname:str)->None:
    # Prevent accidental local-network or metadata-service access from a config.
    # DNS rebinding protection also requires an egress-restricted deployment.
    if hostname.lower() in ("localhost","localhost.localdomain") or hostname.endswith(".local"):
        raise ValueError("Local provider endpoints are forbidden")
    try:
        resolved=socket.getaddrinfo(hostname,443,type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Provider hostname cannot be resolved") from exc
    for item in resolved:
        ip=ipaddress.ip_address(item[4][0])
        if not ip.is_global:raise ValueError("Provider must resolve to public addresses")

def fetch_provider_snapshot(config:ProviderConfig,max_bytes:int=1024*1024)->bytes:
    if not config.enabled:raise ValueError("Provider is disabled")
    if not(config.collection_authorized and config.redistribution_authorized):
        raise ValueError("Provider rights not declared")
    token=os.getenv(config.token_env,"")
    if not token or "\r" in token or "\n" in token:
        raise ValueError("Valid provider bearer token environment variable required")
    hostname=urllib.parse.urlsplit(config.endpoint).hostname
    assert hostname is not None
    _public_host(hostname)
    request=urllib.request.Request(config.endpoint,headers={
        "Authorization":"Bearer "+token,"Accept":"application/json","User-Agent":"ATLAS-Authorized-Feed/1.0"})
    opener=urllib.request.build_opener(NoRedirect,urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(request,timeout=10) as response:
        if response.status!=200:raise ValueError("Provider returned non-200 status")
        if "application/json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("Provider response is not JSON")
        raw=response.read(max_bytes+1)
    if len(raw)>max_bytes:raise ValueError("Provider payload exceeds 1MB")
    snapshot=Snapshot.model_validate_json(raw)
    if snapshot.source_name!=config.name or snapshot.source_url!=config.endpoint:
        raise ValueError("Provider source identity does not match configured endpoint")
    return raw

def sync_provider(config_path:Path,output:Path,apply:bool=False)->dict:
    if config_path.stat().st_size>128*1024:raise ValueError("Provider configuration too large")
    config=ProviderConfig.model_validate_json(config_path.read_bytes())
    raw=fetch_provider_snapshot(config)
    # The existing importer validates every alert and performs atomic updates.
    with tempfile.TemporaryDirectory() as directory:
        snapshot_path=Path(directory)/"provider-snapshot.json"
        snapshot_path.write_bytes(raw)
        result=import_snapshot(snapshot_path,output,dry_run=not apply)
    return {**result,"provider":config.name,"transport":"AUTHORIZED_HTTPS_JSON",
        "live_feed_connected":True,
        "notice":"Provider responded; payload and rights are operator-declared, not independently verified."}

def main():
    parser=argparse.ArgumentParser(description="Fetch authorized provider JSON alert snapshot")
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=Path("../data/notifications/alerts.json"))
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    print(json.dumps(sync_provider(args.config,args.output,apply=args.apply),indent=2))

if __name__=="__main__":main()
