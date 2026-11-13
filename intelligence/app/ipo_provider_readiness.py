"""Offline readiness checks for the opt-in authorized IPO provider adapter.

Never performs DNS resolution, HTTP requests or exposes token values.
"""
import argparse,json,os,urllib.parse
from pathlib import Path
from pydantic import ValidationError
from .authorized_ipo_provider import ProviderConfig

def inspect_provider(config_path:Path)->dict:
    result={"status":"NOT_CONFIGURED","ready":False,"network_requested":False,
        "checks":{},"provider":None,"endpoint_host":None}
    if not config_path.is_file():
        result["checks"]["config_file"]="MISSING"
        return result
    try:
        if config_path.stat().st_size>128*1024:
            raise ValueError("Configuration exceeds 128KB")
        config=ProviderConfig.model_validate_json(config_path.read_bytes())
    except (OSError,ValueError,ValidationError):
        result["status"]="INVALID_CONFIG"
        result["checks"]["config_file"]="INVALID"
        return result
    result["provider"]=config.name
    result["endpoint_host"]=urllib.parse.urlsplit(config.endpoint).hostname
    checks={
        "config_file":"VALID",
        "enabled":"PASS" if config.enabled else "BLOCKED",
        "collection_permission":"DECLARED" if config.collection_authorized else "NOT_DECLARED",
        "redistribution_permission":"DECLARED" if config.redistribution_authorized else "NOT_DECLARED",
        "token_environment":"PRESENT" if bool(os.getenv(config.token_env,"").strip()) else "MISSING"
    }
    result["checks"]=checks
    result["ready"]=config.enabled and config.collection_authorized and config.redistribution_authorized and checks["token_environment"]=="PRESENT"
    result["status"]="READY_FOR_CONNECTION_TEST" if result["ready"] else "BLOCKED"
    return result

def main():
    parser=argparse.ArgumentParser(description="Offline IPO provider readiness check (no network)")
    parser.add_argument("--config",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(inspect_provider(args.config),indent=2))

if __name__=="__main__":main()
