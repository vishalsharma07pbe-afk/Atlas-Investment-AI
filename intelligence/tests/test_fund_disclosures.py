import csv
from datetime import date
import gzip
import io
import tempfile
import unittest
from unittest.mock import patch

from app import fund_disclosures as disclosures, nav_catalog, autonomous_research

TODAY=date(2026,11,25)
STAMP="2026-11-25T04:00:00+00:00"


def row(**changes):
    data={key:"" for key in disclosures.REQUIRED}
    data.update(source="MF",scheme_code="118955",isin="INF179K01BB2",
                scheme_plan="Direct",category_sub="Large Cap Fund",
                amfi_daily_fund_aum_cr_all_plans="3500",amfi_daily_aum_date="2026-11-24",
                amfi_daily_benchmark="Nifty 100 TRI",amfi_daily_riskometer="Very High",
                ssd_doc_date="2026-10-01T00:00:00",ssd_fund_managers="Example Manager",
                ssd_exit_load="1% within one year",ssd_benchmark_tier1_std="Nifty 100 TRI",
                ssd_riskometer_level="Very High",ter_date="2026-11-24",
                ter_direct="0.7",ter_regular="1.4",ter_ber_direct="0.5",ter_ber_regular="1.2")
    data.update(changes)
    return data


def payload(*rows):
    output=io.StringIO(newline="")
    writer=csv.DictWriter(output,fieldnames=sorted(disclosures.REQUIRED))
    writer.writeheader()
    writer.writerows(rows)
    return gzip.compress(output.getvalue().encode())


class FundDisclosuresTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path=patch.object(nav_catalog,"DB_PATH",nav_catalog.Path(directory.name)/"nav.sqlite")
        path.start()
        self.addCleanup(path.stop)
        env=patch.dict("os.environ",{"ATLAS_MF_DISCLOSURE_AUTO_REFRESH_ENABLED":"true",
                                    "MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true"})
        env.start()
        self.addCleanup(env.stop)

    def test_exact_plan_values_and_all_plan_aum(self):
        rows=disclosures.parse(payload(row(),row(scheme_code="118956",scheme_plan="Regular",
                       isin="INF179K01BB3"),row(scheme_code="118957",source="SIF")),TODAY)
        self.assertEqual(set(rows),{"118955","118956"})
        self.assertEqual(rows["118955"]["ter_percent"],0.7)
        self.assertEqual(rows["118956"]["ter_percent"],1.4)
        self.assertEqual(rows["118955"]["aum_cr_all_plans"],3500)
        self.assertEqual(rows["118955"]["status"],"SECONDARY_REPORTED_NOT_INDEPENDENTLY_VERIFIED")

    def test_staleness_conflicts_and_flagged_aum(self):
        item=disclosures.parse(payload(row(amfi_daily_aum_flag="^",
            ssd_benchmark_tier1_std="Other TRI",ssd_riskometer_level="High",
            ter_date="2026-01-01")),TODAY)["118955"]
        self.assertIsNone(item["aum_cr_all_plans"])
        self.assertIsNone(item["ter_percent"])
        self.assertIsNone(item["benchmark"])
        self.assertIsNone(item["riskometer"])
        self.assertEqual(set(item["conflicts"]),{"BENCHMARK_CONFLICT","RISKOMETER_CONFLICT"})

    def test_exact_identity_and_last_good_snapshot(self):
        self.assertEqual(disclosures.store(payload(row()),TODAY,STAMP),1)
        with self.assertRaisesRegex(ValueError,"DISCLOSURE_DUPLICATE_SCHEME"):
            disclosures.store(payload(row(),row()),TODAY,STAMP)
        identity={"scheme_code":118955,"scheme_name":"Example Fund","isin_growth":"INF179K01BB2",
                  "amfi_plan":"DIRECT","amfi_option":"GROWTH",
                  "category":"Open Ended Schemes(Equity Scheme - Large Cap Fund)"}
        self.assertEqual(disclosures.matched([identity],TODAY)[0]["ter_percent"],0.7)
        for changed in ({"isin_growth":"INF179K01BB3"},{"amfi_plan":"REGULAR"},
                        {"amfi_option":"IDCW"},{"category":"Open Ended Schemes(Equity Scheme - Mid Cap Fund)"}):
            self.assertEqual(disclosures.matched([{**identity,**changed}],TODAY),[])
        self.assertEqual(disclosures.matched([identity],date(2026,11,29)),[])

    def test_full_sample_matching_preserves_default_cap_and_identity(self):
        fixtures=[row(scheme_code=str(118955+i)) for i in range(8)]
        self.assertEqual(disclosures.store(payload(*fixtures),TODAY,STAMP),8)
        identities=[{"scheme_code":118955+i,"scheme_name":"Example Fund",
                     "isin_growth":"INF179K01BB2","amfi_plan":"DIRECT","amfi_option":"GROWTH",
                     "category":"Open Ended Schemes(Equity Scheme - Large Cap Fund)"} for i in range(8)]
        self.assertEqual(len(disclosures.matched(identities,TODAY)),5)
        self.assertEqual(len(disclosures.matched(identities,TODAY,limit=40)),8)
        identities[-1]["isin_growth"]="INF179K01BB3"
        self.assertEqual(len(disclosures.matched(identities,TODAY,limit=40)),7)
        self.assertEqual(len(disclosures.matched(identities,TODAY,limit=1)),1)
        self.assertEqual(len(disclosures.matched(identities,TODAY,limit=2)),2)
        for invalid in (0,41,True,2.0,None):
            with self.subTest(limit=invalid), self.assertRaisesRegex(ValueError,"INVALID_DISCLOSURE_MATCH_LIMIT"):
                disclosures.matched(identities,TODAY,limit=invalid)

    def test_full_sample_limit_and_field_expiry_are_independent(self):
        fixtures=[row(scheme_code=str(118955+i),amfi_daily_aum_date="2026-11-11")
                  for i in range(41)]
        self.assertEqual(disclosures.store(payload(*fixtures),TODAY,STAMP),41)
        identities=[{"scheme_code":118955+i,"scheme_name":"Example Fund",
                     "isin_growth":"INF179K01BB2","amfi_plan":"DIRECT","amfi_option":"GROWTH",
                     "category":"Open Ended Schemes(Equity Scheme - Large Cap Fund)"} for i in range(41)]
        tomorrow=date(2026,11,26)
        matched=disclosures.matched(identities,tomorrow,limit=40)
        self.assertEqual([item["scheme_code"] for item in matched],
                         [str(118955+i) for i in range(40)])
        self.assertTrue(all(item["aum_cr_all_plans"] is None for item in matched))
        self.assertTrue(all(item["ter_percent"]==0.7 for item in matched))
        self.assertEqual(len(disclosures.matched(identities,tomorrow)),5)

    def test_requires_explicit_permission(self):
        with patch.dict("os.environ",{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}), \
             patch.object(disclosures.httpx,"Client") as client:
            self.assertEqual(autonomous_research._execute_job("FUND_DISCLOSURES"),"DISABLED_OR_NOT_AUTHORIZED")
            with self.assertRaisesRegex(ValueError,"DISCLOSURE_SOURCE_NOT_AUTHORIZED"):
                disclosures.refresh()
            client.assert_not_called()

    def test_scheduler_uses_existing_collection(self):
        with patch.object(disclosures,"refresh",return_value=1) as collect:
            self.assertEqual(autonomous_research._execute_job("FUND_DISCLOSURES"),"PASS_COMPLETED")
            collect.assert_called_once()

    def test_disclosure_audit_is_atomic_and_corrupt_row_isolated(self):
        from contextlib import closing
        from datetime import datetime,timezone
        disclosures.store(payload(row(),row(scheme_code="118956",isin="INF179K01BB3"),
            row(scheme_code="118957",isin="INE002A01018")),TODAY,STAMP)
        instant=datetime(2026,11,25,5,tzinfo=timezone.utc)
        report=disclosures.ingestion_coverage(instant)
        self.assertEqual(report["source_counts"],{"ACCEPTED":2,"INVALID_IDENTITY_OR_PLAN":1})
        self.assertEqual(report["fresh_field_counts"]["ter_percent"],2)
        with self.assertRaises(ValueError):
            disclosures.store(payload(row(),row()),TODAY,STAMP)
        self.assertEqual(disclosures.ingestion_coverage(instant),report)
        with closing(nav_catalog._connect()) as db,db:
            db.execute("UPDATE fund_disclosure_snapshot SET payload='invalid' WHERE scheme_code='118955'")
        items=[{"scheme_code":code,"scheme_name":"Example","isin_growth":isin,"amfi_plan":"DIRECT",
                "amfi_option":"GROWTH","category":"Open Ended Schemes(Equity Scheme - Large Cap Fund)"}
               for code,isin in ((118955,"INF179K01BB2"),(118956,"INF179K01BB3"))]
        self.assertEqual([r["scheme_code"] for r in disclosures.matched(items,TODAY)],["118956"])
        self.assertEqual(disclosures.ingestion_coverage(instant)["stored_counts"]["INVALID_STORED_ROW"],1)

    def test_shared_publisher_cooldown_blocks_both_bulk_jobs(self):
        from datetime import datetime,timezone,timedelta
        import httpx
        from app import fund_portfolios
        now=datetime.now(timezone.utc)
        request=httpx.Request("GET",disclosures.URL)
        response=httpx.Response(429,request=request,headers={"Retry-After":"86400"})
        try:response.raise_for_status()
        except httpx.HTTPStatusError as error:disclosures.record_bulk_failure(error,now)
        self.assertEqual(disclosures.bulk_cooldown(now)["reason"],"RATE_LIMITED")
        self.assertIsNone(disclosures.bulk_cooldown(now+timedelta(days=2)))
        with patch.object(disclosures.httpx,"Client") as client:
            self.assertEqual(disclosures.refresh(),0)
            self.assertEqual(fund_portfolios.refresh(),0)
            self.assertEqual(autonomous_research._execute_job("FUND_DISCLOSURES"),"WAITING_EVIDENCE")
            self.assertEqual(autonomous_research._execute_job("FUND_PORTFOLIOS"),"WAITING_EVIDENCE")
            client.assert_not_called()
