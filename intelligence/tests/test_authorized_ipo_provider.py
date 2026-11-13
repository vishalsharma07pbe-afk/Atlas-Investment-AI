import io,json,os,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from app.authorized_ipo_provider import ProviderConfig,fetch_provider_snapshot,sync_provider

ENDPOINT="https://licensed.example.org/alerts"
def config(**kwargs):
    return {"name":"Licensed provider","endpoint":ENDPOINT,
        "token_env":"ATLAS_PROVIDER_IPO_TOKEN","enabled":True,
        "collection_authorized":True,"redistribution_authorized":True,**kwargs}
def payload():
    published=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
    retrieved=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    return json.dumps({"source_name":"Licensed provider","source_url":ENDPOINT,
        "retrieved_at":retrieved,"collection_authorized":True,
        "redistribution_authorized":True,"alerts":[{
            "id":"example-ipo","category":"IPO_UPCOMING","title":"Example IPO",
            "description":"Test only","event_date":"2026-11-20",
            "published_at":published,"source_name":"Licensed provider",
            "source_url":ENDPOINT}]}).encode()
class Response:
    status=200
    headers={"Content-Type":"application/json"}
    def __init__(self,data):self.data=io.BytesIO(data)
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.data.read(n)
class ProviderTests(unittest.TestCase):
    def test_permissions_and_https_required(self):
        with self.assertRaises(ValidationError):ProviderConfig.model_validate({**config(),"enabled":True,"collection_authorized":False})
        with self.assertRaises(ValidationError):ProviderConfig.model_validate({**config(),"endpoint":"http://example.org/alerts"})
        with self.assertRaises(ValidationError):ProviderConfig.model_validate({**config(),"endpoint":"https://localhost/alerts"})
    def test_no_token_prevents_fetch(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):fetch_provider_snapshot(ProviderConfig.model_validate(config()))
    def test_dry_run_then_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg=root/"provider.json";out=root/"alerts.json"
            cfg.write_text(json.dumps(config()))
            with patch.dict(os.environ,{"ATLAS_PROVIDER_IPO_TOKEN":"test-token"}),patch("app.authorized_ipo_provider._public_host"),patch("urllib.request.OpenerDirector.open",side_effect=lambda *args,**kwargs:Response(payload())):
                result=sync_provider(cfg,out)
                self.assertEqual(result["status"],"DRY_RUN")
                self.assertFalse(out.exists())
                result=sync_provider(cfg,out,apply=True)
                self.assertEqual(result["added"],1)
                self.assertEqual(json.loads(out.read_text())[0]["id"],"example-ipo")
    def test_source_mismatch_rejected(self):
        invalid=json.loads(payload());invalid["source_name"]="Unrecognized provider"
        with patch.dict(os.environ,{"ATLAS_PROVIDER_IPO_TOKEN":"test-token"}),patch("app.authorized_ipo_provider._public_host"),patch("urllib.request.OpenerDirector.open",return_value=Response(json.dumps(invalid).encode())):
            with self.assertRaises(ValueError):fetch_provider_snapshot(ProviderConfig.model_validate(config()))
if __name__=="__main__":unittest.main()
