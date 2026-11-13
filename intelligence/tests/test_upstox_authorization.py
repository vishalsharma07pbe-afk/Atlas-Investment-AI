import json
import unittest
from io import BytesIO
from urllib.error import HTTPError
from app.upstox_authorization import authorize_feed,authorization_diagnostics,AuthorizationError,AUTHORIZE_URL

class FakeResponse:
    status=200
    def __init__(self,data):self.data=BytesIO(json.dumps(data).encode())
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.data.read(n)

class FakeOpener:
    def __init__(self,data):self.data=data;self.request=None
    def open(self,request,timeout):self.request=request;return FakeResponse(self.data)

class UpstoxAuthorizationTests(unittest.TestCase):
    def test_success_and_authorization_header(self):
        uri="wss://feed.upstox.com/market-data-feeder/v3?code=secret"
        client=FakeOpener({"status":"success","data":{"authorized_redirect_uri":uri}})
        self.assertEqual(authorize_feed("private-token",client),uri)
        self.assertEqual(client.request.full_url,AUTHORIZE_URL)
        self.assertEqual(client.request.get_header("Authorization"),"Bearer private-token")

    def test_reject_untrusted_signed_redirect(self):
        client=FakeOpener({"status":"success","data":{"authorized_redirect_uri":"wss://evil.test/?code=secret"}})
        with self.assertRaisesRegex(AuthorizationError,"untrusted"):
            authorize_feed("private-token",client)

    def test_reject_malformed_response_without_secrets(self):
        for payload in ({},{"status":"error","data":{}},{"status":"success","data":{"authorized_redirect_uri":123}}):
            with self.subTest(payload=payload):
                with self.assertRaises(AuthorizationError) as context:
                    authorize_feed("private-token",FakeOpener(payload))
                self.assertNotIn("private-token",str(context.exception))

    def test_fail_closed_without_entitlement(self):
        result=authorization_diagnostics("UPSTOX",True,False,True)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertFalse(result["live_stream_connected"])
        self.assertNotIn("token",str(result).lower().replace("access_token_missing",""))

    def test_missing_token(self):
        with self.assertRaises(AuthorizationError):
            authorize_feed("")

if __name__=="__main__":unittest.main()
