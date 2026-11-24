#!/usr/bin/env python3
"""Verify checksums and archive path safety without restoring any data."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path, PurePosixPath
import tarfile


EXPECTED = ("postgres.dump", "intelligence-state.tar.gz")
STATE_ROOTS = {"nav-data", "ingestion-data", "flow-data", "news-data", "reliability-data", "journal"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify(directory: Path) -> dict:
    if not directory.is_dir():
        raise ValueError("BACKUP_DIRECTORY_NOT_FOUND")
    checksum_file = directory / "SHA256SUMS"
    if not checksum_file.is_file():
        raise ValueError("CHECKSUM_FILE_MISSING")
    expected = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if (len(parts) != 2 or parts[1] not in EXPECTED
                or parts[1] in expected or not re.fullmatch(r"[0-9a-f]{64}", parts[0])):
            raise ValueError("INVALID_CHECKSUM_MANIFEST")
        expected[parts[1]] = parts[0]
    if set(expected) != set(EXPECTED):
        raise ValueError("INCOMPLETE_CHECKSUM_MANIFEST")
    for name in EXPECTED:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0 or digest(path) != expected[name]:
            raise ValueError(f"CHECKSUM_MISMATCH:{name}")
    member_count = 0
    seen = set()
    with tarfile.open(directory / "intelligence-state.tar.gz", "r:gz") as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if (not name.parts or name.parts[0] not in STATE_ROOTS
                    or name in seen or name.is_absolute() or ".." in name.parts or member.issym()
                    or member.islnk() or not (member.isfile() or member.isdir())):
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
            seen.add(name)
            member_count += 1
    return {"status": "VERIFIED", "files": list(EXPECTED),
            "intelligence_state_members": member_count,
            "note": "Integrity verified only; a separate isolated restore drill is still required."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_directory", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.backup_directory)
    except (OSError, ValueError, tarfile.TarError) as exc:
        print({"status": "FAILED", "error": str(exc)})
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
