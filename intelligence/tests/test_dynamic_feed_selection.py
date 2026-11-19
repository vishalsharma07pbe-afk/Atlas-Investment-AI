import asyncio
from types import SimpleNamespace

from app import dynamic_feed_selection as module


class FakeSupervisor:
    def __init__(self,keys=()):
        self.worker=SimpleNamespace(active_keys=set(keys))
        self.selected_count=len(keys)
        self.startup_result={}
        self.stops=0
        self.starts=[]
    async def stop(self):
        self.stops+=1
        self.worker.active_keys.clear()
        self.selected_count=0
    async def start(self,**kwargs):
        self.starts.append(kwargs["keys"])
        self.worker.active_keys=set(kwargs["keys"])
        self.selected_count=len(kwargs["keys"])
        return {"status":"STARTING"}


def configured(monkeypatch):
    monkeypatch.setattr(module,"settings",SimpleNamespace(
        provider="UPSTOX",upstox_token="redacted-test-token",
        licensed_data_access=True,entitlement_confirmed=True,
        backend_url="http://backend:8080"))
    monkeypatch.delenv("ATLAS_UPSTOX_INSTRUMENT_IDS",raising=False)
    monkeypatch.delenv("ATLAS_UPSTOX_INSTRUMENT_KEYS",raising=False)
    monkeypatch.setenv("ATLAS_UPSTOX_FEED_ENABLED","true")


def test_reconcile_subscribes_to_resolved_portfolio_symbols(monkeypatch):
    configured(monkeypatch)
    supervisor=FakeSupervisor()
    monkeypatch.setattr(module,"feed_supervisor",supervisor)
    selector=module.DynamicFeedSelection()
    monkeypatch.setattr(selector,"_fetch",lambda:{
        "holding_symbol_count":1,
        "subscriptions":[{"symbol":"RELIANCE","instrument_key":"NSE_EQ|INE002A01018"}],
        "missing_symbols":[],
    })
    result=asyncio.run(selector.reconcile())
    assert result["status"]=="STARTING"
    assert len(supervisor.starts)==1
    assert set(supervisor.starts[0])==module.INDEX_KEYS|{"NSE_EQ|INE002A01018"}
    assert result["resolved_count"]==1


def test_reconcile_keeps_index_stream_when_last_equity_is_removed(monkeypatch):
    configured(monkeypatch)
    supervisor=FakeSupervisor(["NSE_EQ|INE002A01018"])
    monkeypatch.setattr(module,"feed_supervisor",supervisor)
    selector=module.DynamicFeedSelection()
    monkeypatch.setattr(selector,"_fetch",lambda:{
        "holding_symbol_count":0,"subscriptions":[],"missing_symbols":[]})
    result=asyncio.run(selector.reconcile())
    assert result["status"]=="STARTING"
    assert supervisor.stops==1
    assert len(supervisor.starts)==1
    assert set(supervisor.starts[0])==module.INDEX_KEYS


def test_explicit_environment_selection_remains_a_fallback(monkeypatch):
    configured(monkeypatch)
    monkeypatch.setenv("ATLAS_UPSTOX_INSTRUMENT_KEYS","NSE_EQ|INE002A01018")
    supervisor=FakeSupervisor(["NSE_EQ|INE002A01018"])
    monkeypatch.setattr(module,"feed_supervisor",supervisor)
    result=asyncio.run(module.DynamicFeedSelection().reconcile())
    assert result["mode"]=="EXPLICIT_ENV_FALLBACK"
    assert supervisor.stops==1
    assert set(supervisor.starts[0])==module.INDEX_KEYS|{"NSE_EQ|INE002A01018"}
