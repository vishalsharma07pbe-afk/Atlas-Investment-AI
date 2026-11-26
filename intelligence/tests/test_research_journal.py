import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from uuid import uuid4
from urllib.error import HTTPError
from starlette.requests import Request
from app import journal_session
from pydantic import ValidationError
from fastapi import HTTPException
from app import main
from app.research_journal import JournalEntryInput,list_entries,create_entry,update_entry,delete_entry

def note(status="IDEA"):
    return JournalEntryInput(symbol="TEST",thesis="Synthetic research thesis",evidence="Synthetic evidence",risks="Synthetic risk",status=status)

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env=patch.dict("os.environ",{"ATLAS_RESEARCH_JOURNAL_FILE":str(Path(self.temp.name)/"journal.json")})
        self.env.start();self.addCleanup(self.env.stop)
    def test_create_read_update_delete(self):
        self.assertEqual(list_entries(),[])
        created=create_entry(note())
        self.assertEqual(len(list_entries()),1)
        self.assertEqual(list_entries()[0]["id"],created["id"])
        updated=update_entry(created["id"],note("MONITORING"))
        self.assertEqual(updated["status"],"MONITORING")
        self.assertEqual(updated["created_at"],created["created_at"])
        self.assertTrue(delete_entry(created["id"]))
        self.assertEqual(list_entries(),[])
        self.assertFalse(delete_entry(created["id"]))
    def test_invalid_payload_rejected(self):
        with self.assertRaises(ValidationError):
            JournalEntryInput(symbol="BAD SYMBOL",thesis="ok")
    def test_corrupt_storage_fails_closed(self):
        Path(self.temp.name,"journal.json").write_text("{invalid")
        with self.assertRaises(ValueError):list_entries()
    def test_api_endpoints(self):
        owner=uuid4()
        request=MagicMock()
        with patch.object(main,"journal_owner",return_value=owner):
            created=main.journal_create(note(),request)
            self.assertEqual(main.journal_list(request)["entries"][0]["id"],created["id"])
            self.assertEqual(main.journal_update(created["id"],note("CLOSED"),request)["status"],"CLOSED")
            main.journal_delete(created["id"],request)
            with self.assertRaises(HTTPException) as context:main.journal_delete(created["id"],request)
            self.assertEqual(context.exception.status_code,404)

    def test_legacy_notes_preserved_and_never_automatically_assigned(self):
        legacy=create_entry(note())
        a,b=uuid4(),uuid4()
        request=MagicMock()
        with patch.object(main,"journal_owner",return_value=a):
            self.assertEqual(main.journal_list(request),{"entries":[]})
            item=main.journal_create(note(),request)
        with patch.object(main,"journal_owner",return_value=b):
            self.assertEqual(main.journal_list(request),{"entries":[]})
            for call in (lambda:main.journal_update(item["id"],note("CLOSED"),request),
                         lambda:main.journal_delete(item["id"],request)):
                with self.assertRaises(HTTPException) as context:call()
                self.assertEqual(context.exception.status_code,404)
        self.assertEqual(list_entries(a)[0]["id"],item["id"])
        self.assertEqual(list_entries()[0]["id"],legacy["id"])

    def test_session_authority_ignores_claimed_owner_and_rejects_revoked_session(self):
        owner=uuid4()
        request=Request({"type":"http","method":"GET","path":"/","headers":[
            (b"authorization",b"Bearer disposable"),(b"x-atlas-owner",str(uuid4()).encode())]})
        with patch.object(journal_session,"build_opener") as build:
            response=build.return_value.open.return_value.__enter__.return_value
            response.read.return_value=('{"id":"'+str(owner)+'"}').encode()
            self.assertEqual(journal_session.owner_for(request,"http://backend:8080"),owner)
            call=build.return_value.open.call_args.args[0]
            self.assertEqual(call.full_url,"http://backend:8080/api/v1/auth/me")
            self.assertEqual(call.get_header("Authorization"),"Bearer disposable")
            build.return_value.open.side_effect=HTTPError(call.full_url,401,"",{},None)
            with self.assertRaises(HTTPException) as context:journal_session.owner_for(request,"http://backend:8080")
            self.assertEqual(context.exception.status_code,401)

    def test_cookie_cross_origin_and_missing_session_are_blocked_before_backend(self):
        cross=Request({"type":"http","method":"POST","path":"/","headers":[
            (b"cookie",b"ATLAS_SESSION=disposable"),(b"sec-fetch-site",b"cross-site")]})
        anonymous=Request({"type":"http","method":"GET","path":"/","headers":[]})
        with patch.object(journal_session,"build_opener") as build:
            for req,status in ((cross,403),(anonymous,401)):
                with self.assertRaises(HTTPException) as context:journal_session.owner_for(req,"http://backend:8080")
                self.assertEqual(context.exception.status_code,status)
            build.assert_not_called()
if __name__=="__main__":unittest.main()
