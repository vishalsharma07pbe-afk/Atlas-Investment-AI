import json,tempfile,unittest
from datetime import date,datetime,timezone
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from app import independent_valuation as v

TODAY=date(2026,11,28)
def evidence():
    return {"isin":"INE002A01018","operator_reviewed":True,"scope":"CONSOLIDATED_INR_CRORE",
      "model":"FCFF","sector_type":"NON_FINANCIAL","fiscal_period_end":"2026-03-31","review_date":"2026-11-26",
      "price_date":"2026-11-27","price_basis":"ACTUAL_UNADJUSTED_INR","same_share_basis":True,
      "diluted_shares_cr":10,"price_inr":100,"net_debt_cr":20,"ebit_cr":100,"depreciation_cr":10,
      "capex_cr":20,"working_capital_increase_cr":5,"tax_rate_percent":25,
      "scenarios":[{"case":k,"growth_percent":g,"discount_percent":d,"terminal_growth_percent":2,
                    "next_year_net_profit_cr":profit} for k,g,d,profit in (("BEAR",0,15,60),("BASE",5,12,70),("BULL",10,10,80))]}

class IndependentValuationTest(unittest.TestCase):
    def test_source_bound_cash_and_scenarios(self):
        row=evidence();out=v.scenario(row,TODAY)
        self.assertEqual(out["cash_base_cr"],60)
        self.assertEqual(out["scenarios"][1]["conditional_eps"],7)
        self.assertLess(out["scenarios"][0]["conditional_value_per_share"],out["scenarios"][2]["conditional_value_per_share"])
        self.assertFalse(out["qualified"])
        self.assertIsNone(v.scenario({**row,"price_basis":"ADJUSTED"},TODAY))
        self.assertIsNone(v.scenario({**row,"sector_type":"FINANCIAL"},TODAY))
        self.assertIsNone(v.scenario({**row,"price_date":"2026-11-15"},TODAY))
        self.assertIsNone(v.scenario({**row,"capex_cr":None},TODAY))

    def test_source_hash_and_permission(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"valuation-evidence.json"
            row=evidence();row["sources"]=[]
            for i,role in enumerate(("FINANCIAL_STATEMENTS","SHARE_AND_PRICE_BASIS","VALUATION_ASSUMPTIONS")):
                name=f"document-{i}.txt";body=f"test document {i}".encode()
                (p.parent/name).write_bytes(body)
                row["sources"].append({"role":role,"file":name,"sha256":sha256(body).hexdigest()})
            p.write_text(json.dumps({"methodology":v.VERSION,"authorization_attested":True,"companies":[row]}))
            now=datetime(2026,11,28,6,tzinfo=timezone.utc)
            with patch.object(v,"permitted",return_value=False):
                self.assertEqual(v.read(now,p),{})
            with patch.object(v,"permitted",return_value=True):
                self.assertIn(row["isin"],v.read(now,p))
                self.assertEqual(v.read(now,p,identities={"INE467B01029"}),{})
                (p.parent/"document-0.txt").write_text("changed")
                self.assertEqual(v.read(now,p),{})


    def test_reverse_valuation_recovers_declared_growth_at_exact_model_price(self):
        cash,shares,debt=60,10,20
        price=v.discounted_equity(cash,7,12,2,debt)/shares
        reverse=v.implied_growth(cash,shares,price,12,2,debt)
        self.assertAlmostEqual(reverse["growth_percent"],7,places=4)
        self.assertIsNone(v.implied_growth(cash,shares,10000000,12,2,debt)["growth_percent"])
