import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import economic_calendar as calendar, autonomous_research as research

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)

def fixture():
    return ("\r\n".join(["BEGIN:VCALENDAR","VERSION:2.0",
        "BEGIN:VEVENT","UID:cpi-1","SUMMARY:Consumer Price Index",
        "DTSTART;TZID=America/New_York:20261126T083000","END:VEVENT",
        "BEGIN:VEVENT","UID:jobs-1","SUMMARY:Employment Situa"," tion",
        "DTSTART:20261125T103000Z","END:VEVENT",
        "BEGIN:VEVENT","UID:ppi-1","SUMMARY:Producer Price Index",
        "DTSTART:20261127T133000Z","STATUS:CANCELLED","END:VEVENT","END:VCALENDAR"])+"\r\n").encode()

class EconomicCalendarTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":root.name+"/research.sqlite",
            "MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true","ATLAS_ECONOMIC_CALENDAR_ENABLED":"true"})
        env.start()
        self.addCleanup(env.stop)

    def test_schedule_not_publication_and_timezones(self):
        rows=calendar.parse(fixture(),NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["headline"],"Employment Situation")
        self.assertEqual(rows[1]["scheduled_at"],"2026-11-26T13:30:00+00:00")
        calendar.refresh(research._connect,NOW,lambda _:rows)
        result=calendar.read(research._connect,NOW+timedelta(hours=2))
        self.assertEqual(result["events"][0]["status"],"SCHEDULE_TIME_PASSED_RELEASE_UNVERIFIED")
        self.assertTrue(result["events"][1]["review_window"])
        self.assertEqual(calendar.read(research._connect,NOW+timedelta(hours=25))["status"],"STALE_CAPTURE")

    def test_invalid_and_recurrent_schedules_fail_closed(self):
        for raw in (fixture().replace(b"America/New_York",b"UNKNOWN"),
                    fixture().replace(b"UID:jobs-1",b"UID:cpi-1"),
                    fixture().replace(b"UID:cpi-1",b"UID:cpi-1\r\nRRULE:FREQ=DAILY"),
                    fixture().replace(b"END:VCALENDAR",b""),
                    fixture().replace(b"20261126T083000",b"20261101T013000")):
            with self.assertRaises(ValueError):
                calendar.parse(raw,NOW)

    def test_reschedule_replaces_previous_snapshot(self):
        calendar.refresh(research._connect,NOW,lambda instant:calendar.parse(fixture(),instant))
        calendar.refresh(research._connect,NOW+timedelta(hours=1),
            lambda instant:calendar.parse(fixture().replace(b"20261126T083000",b"20261127T083000"),instant))
        rows=calendar.read(research._connect,NOW+timedelta(hours=1))["events"]
        self.assertEqual(rows[1]["scheduled_at"],"2026-11-27T13:30:00+00:00")
        self.assertEqual(len(rows),2)

    def test_gate(self):
        with patch.dict(os.environ,{"ATLAS_ECONOMIC_CALENDAR_ENABLED":"false"}):
            self.assertEqual(research._execute_job("ECONOMIC_CALENDAR"),"DISABLED_OR_NOT_AUTHORIZED")
