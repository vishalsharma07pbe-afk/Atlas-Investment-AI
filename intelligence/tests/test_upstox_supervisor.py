import asyncio
import unittest
from app.upstox_supervisor import FeedSupervisor
from app.upstox_quote_worker import QuoteWorker

KEY="NSE_EQ|INE002A01018"

class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_and_missing_credentials(self):
        supervisor=FeedSupervisor(QuoteWorker())
        self.assertEqual((await supervisor.start(enabled=False,keys=[KEY],token=None,provider="UPSTOX",rights=True,entitlement=True))["status"],"DISABLED")
        self.assertEqual((await supervisor.start(enabled=True,keys=[KEY],token=None,provider="UPSTOX",rights=True,entitlement=True))["status"],"BLOCKED")
        self.assertFalse(supervisor.status()["supervised_task_running"])
    async def test_invalid_key_never_starts(self):
        supervisor=FeedSupervisor(QuoteWorker())
        result=await supervisor.start(enabled=True,keys=["INVALID"],token="secret",provider="UPSTOX",rights=True,entitlement=True)
        self.assertEqual(result["status"],"BLOCKED")
    async def test_shutdown_is_idempotent(self):
        supervisor=FeedSupervisor(QuoteWorker())
        await supervisor.stop()
        await supervisor.stop()
        self.assertFalse(supervisor.worker.cache.connected)

    async def test_credential_rejection_cooldown_survives_stop(self):
        class Worker(QuoteWorker):
            async def run(self,*args,**kwargs):
                return {"status":"DISCONNECTED","last_failure":"FEED_CREDENTIAL_REJECTED"}
        ticks=[0]
        supervisor=FeedSupervisor(Worker(),clock=lambda:ticks[0])
        config=dict(enabled=True,keys=[KEY],token="secret",provider="UPSTOX",rights=True,entitlement=True)
        self.assertEqual((await supervisor.start(**config))["status"],"STARTING")
        await supervisor.task
        self.assertEqual(supervisor.status()["retry_after_seconds"],900)
        await supervisor.stop()
        self.assertEqual((await supervisor.start(**config))["status"],"RECOVERY_COOLDOWN")
        self.assertEqual(supervisor.requested_keys,{KEY})
        ticks[0]=901
        self.assertEqual((await supervisor.start(**config))["status"],"STARTING")
        await supervisor.stop()

if __name__=="__main__":unittest.main()
