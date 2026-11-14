import json
import unittest
from pydantic import ValidationError
from app.ai_verdict import parse_verdict

def valid():
    return {"action":"BUY","confidence":0.75,"target_1":110.0,"target_2":120.0,
            "stop_loss":90.0,"holding_horizon":"SWING",
            "pros":["Momentum positive"],"cons":["Liquidity risk"]}

class VerdictContractTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_verdict(json.dumps(valid())).action,"BUY")
    def test_extra_field_forbidden(self):
        with self.assertRaises(ValidationError):
            parse_verdict(json.dumps({**valid(),"account_id":"secret"}))
    def test_missing_field_forbidden(self):
        item=valid()
        del item["cons"]
        with self.assertRaises(ValidationError):
            parse_verdict(json.dumps(item))
    def test_confidence_and_levels(self):
        for change in ({"confidence":1.2},{"stop_loss":115.0},
                       {"action":"HOLD"},{"target_1":float("nan")}):
            with self.assertRaises(ValidationError):
                parse_verdict(json.dumps({**valid(),**change}))
    def test_no_markdown(self):
        with self.assertRaisesRegex(ValueError,"VERDICT_NOT_JSON"):
            parse_verdict("```json\n{}\n```")
    def test_reject_sensitive_reason(self):
        with self.assertRaises(ValidationError):
            parse_verdict(json.dumps({**valid(),"pros":["access_token=secret"]}))
if __name__=="__main__":
    unittest.main()
