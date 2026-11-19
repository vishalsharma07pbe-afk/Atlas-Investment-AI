"""Stream a path-bounded archive of ATLAS intelligence state to stdout.

Run only while the intelligence service is stopped so SQLite files are quiescent.
The archive can contain private research data and must be encrypted by the operator.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tarfile


ROOTS = (
    Path("/app/nav-data"), Path("/app/ingestion-data"), Path("/app/flow-data"),
    Path("/app/news-data"), Path("/app/reliability-data"), Path("/app/journal"),
)


def safe_members():
    for root in ROOTS:
        if not root.exists() or root.is_symlink():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve()
            if root.resolve() not in resolved.parents:
                continue
            yield path, Path(root.name) / path.relative_to(root)


def main() -> int:
    # Never write archive bytes to a terminal by mistake.
    if sys.stdout.isatty():
        print("Refusing to write a binary backup to a terminal.", file=sys.stderr)
        return 2
    os.umask(0o077)
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
        for source, name in safe_members():
            archive.add(source, arcname=str(name), recursive=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

