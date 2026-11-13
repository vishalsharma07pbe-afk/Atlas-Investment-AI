import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
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
        created=main.journal_create(note())
        self.assertEqual(main.journal_list()["entries"][0]["id"],created["id"])
        self.assertEqual(main.journal_update(created["id"],note("CLOSED"))["status"],"CLOSED")
        main.journal_delete(created["id"])
        with self.assertRaises(HTTPException) as context:main.journal_delete(created["id"])
        self.assertEqual(context.exception.status_code,404)
if __name__=="__main__":unittest.main()
