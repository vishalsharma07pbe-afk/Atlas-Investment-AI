import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = load("p3_smoke", "scripts/p3_smoke.py")
acceptance = load("local_research_acceptance", "scripts/local_research_acceptance.py")
verify_backup = load("verify_backup", "scripts/verify-production-backup.py")
ops_snapshot = load("ops_snapshot", "intelligence/app/ops_snapshot.py")


class P3SmokeTests(unittest.TestCase):
    def test_production_intelligence_route_requires_application_session(self):
        nginx = (ROOT / "frontend/trading-dashboard/nginx.production.conf").read_text(
            encoding="utf-8")
        self.assertIn("location /intelligence/ {\n    auth_request /_atlas_auth;", nginx)
        self.assertIn("location = /_atlas_auth {", nginx)
        self.assertIn("proxy_pass http://backend:8080/api/v1/auth/me;", nginx)

    def test_remote_target_requires_explicit_operator_consent(self):
        with self.assertRaisesRegex(ValueError, "REMOTE_TARGET"):
            smoke.validate_base_url("https://example.com")
        self.assertEqual(smoke.validate_base_url("https://example.com", True),
                         "https://example.com")

    def test_load_thresholds_pass_and_fail(self):
        with patch.object(smoke, "request_once", return_value=(True, 12.0, 200)):
            result = smoke.run("http://localhost:8088", 10, 2, 1, 50, 0)
        self.assertEqual(result["status"], "PASS")
        with patch.object(smoke, "request_once", return_value=(False, 80.0, 503)):
            result = smoke.run("http://localhost:8088", 5, 1, 1, 50, 1)
        self.assertEqual(result["status"], "FAIL")


class LocalAcceptanceTests(unittest.TestCase):
    def fixture(self):
        readiness = {"automatic_research_enabled": True, "actionable_recommendations_enabled": False,
                     "provider_mode": "UPSTOX", "blockers": [], "live_market_data_connected": False,
                     "backend_evidence": [{"code": c, "status": "RECENT_LOCAL_EVIDENCE", "records": 1}
                                          for c in acceptance.SOURCES]}
        overview = {"enabled": True, "scope": "PUBLIC_MARKET_RESEARCH_ONLY", "sections": [
            {"section": key, "status": "READY", "result": {"eligible_count": 1} if key in ("NSE","BSE")
             else {"historical_coverage": {"status": "HISTORICAL_WATCH_ONLY", "items": [{"private": "never-printed"}]}}}
            for key in sorted(acceptance.SECTIONS)]}
        review = {"holding_count": 1, "holdings": [{"symbol": "PRIVATE_MARKER"}],
                  "diversification": {}, "opportunity_context": {"status": "WATCH_EVIDENCE_AVAILABLE"}}
        return readiness, overview, review

    def test_stored_data_and_live_status_are_independent(self):
        r, o, p = self.fixture()
        result = acceptance.assess(r, o, p)
        self.assertEqual(result["runtime"], "PASS")
        self.assertEqual(result["stored_provider_evidence"], "PASS")
        self.assertEqual(result["live_feed"], "NOT_OBSERVED")
        self.assertNotIn("PRIVATE_MARKER", str(result))
        self.assertNotIn("never-printed", str(result))

    def test_empty_and_stale_sources_cannot_pass(self):
        r, o, p = self.fixture()
        r["backend_evidence"][0]["records"] = 0
        o["sections"][0]["status"] = "STALE"
        self.assertEqual(acceptance.assess(r, o, p)["runtime"], "BLOCKED")
        self.assertEqual(acceptance.assess(r, o, p)["stored_provider_evidence"], "BLOCKED")

    def test_remote_gateway_rejected_before_network_request(self):
        with self.assertRaisesRegex(ValueError, "LOOPBACK"):
            acceptance.LocalSession("https://example.com")
        self.assertIsNone(acceptance.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))


class BackupVerificationTests(unittest.TestCase):
    def test_verifies_checksums_and_safe_archive_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "postgres.dump").write_bytes(b"pg-data")
            with tarfile.open(root / "intelligence-state.tar.gz", "w:gz") as archive:
                content = b"state"
                info = tarfile.TarInfo("nav-data/catalog.sqlite3")
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
            lines = []
            for name in verify_backup.EXPECTED:
                lines.append(f"{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}")
            (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = verify_backup.verify(root)
            self.assertEqual(result["status"], "VERIFIED")
            self.assertEqual(result["intelligence_state_members"], 1)

    def test_rejects_archive_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "postgres.dump").write_bytes(b"pg-data")
            with tarfile.open(root / "intelligence-state.tar.gz", "w:gz") as archive:
                info = tarfile.TarInfo("../escape")
                info.size = 1
                archive.addfile(info, io.BytesIO(b"x"))
            lines = [f"{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}"
                     for name in verify_backup.EXPECTED]
            (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE"):
                verify_backup.verify(root)

    def test_rejects_unexpected_root_and_duplicate_archive_members(self):
        for names in (["unexpected/file.sqlite3"], ["nav-data/a.sqlite3", "nav-data/a.sqlite3"]):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "postgres.dump").write_bytes(b"pg-data")
                with tarfile.open(root / "intelligence-state.tar.gz", "w:gz") as archive:
                    for name in names:
                        info = tarfile.TarInfo(name)
                        info.size = 1
                        archive.addfile(info, io.BytesIO(b"x"))
                lines = [f"{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}"
                         for name in verify_backup.EXPECTED]
                (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "UNSAFE_ARCHIVE"):
                    verify_backup.verify(root)

    def test_rejects_empty_backup_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "postgres.dump").write_bytes(b"")
            with tarfile.open(root / "intelligence-state.tar.gz", "w:gz"):
                pass
            lines = [f"{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}"
                     for name in verify_backup.EXPECTED]
            (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CHECKSUM_MISMATCH"):
                verify_backup.verify(root)

    def test_snapshot_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "nav-data"
            root.mkdir()
            (root / "catalog.sqlite3").write_bytes(b"state")
            (root / "outside-link").symlink_to(Path(directory) / "outside")
            with patch.object(ops_snapshot, "ROOTS", (root,)):
                members = list(ops_snapshot.safe_members())
            self.assertEqual([name.as_posix() for _, name in members],
                             ["nav-data/catalog.sqlite3"])


if __name__ == "__main__":
    unittest.main()

