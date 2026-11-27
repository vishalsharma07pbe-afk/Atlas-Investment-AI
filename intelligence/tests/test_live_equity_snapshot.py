from datetime import datetime,timezone
from unittest.mock import patch
from app.live_events import equity_snapshot

def test_equity_snapshot_only_live_subscribed_equities():
    from app.upstox_quote_worker import quote_worker
    key="NSE_EQ|INE002A01018"
    stamp=datetime.now(timezone.utc).isoformat()
    def snapshot(k):
        return {"status":"LIVE","quote":{"instrument_key":k,"last_traded_price":123.5,"previous_close":120,"traded_at":stamp,"age_ms":0}} if k==key else {"status":"STALE","quote":None}
    with patch.object(quote_worker,"running",True),patch.object(quote_worker,"active_keys",{key,"NSE_EQ|INE009A01021","NSE_INDEX|Nifty 50"}),patch.object(quote_worker.cache,"connected",True),patch.object(quote_worker.cache,"snapshot",side_effect=snapshot):
        result=equity_snapshot()
        assert result["status"]=="AVAILABLE"
        assert result["items"]==[{"instrument_key":key,"price":123.5,"previous_close":120,"as_of":stamp}]
    with patch.object(quote_worker,"running",True),patch.object(quote_worker.cache,"connected",False):
        assert equity_snapshot()["items"]==[]
