#!/usr/bin/env python3

from __future__ import annotations

import gzip
import os
import shutil
import sys
import tempfile
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = APP_ROOT / "app" / "data" / "phrc_bgcstructdb.sqlite"
COMPRESSED_DATABASE = APP_ROOT / "app" / "data" / "phrc_bgcstructdb.sqlite.gz"
SQLITE_HEADER = b"SQLite format 3\x00"


def resolve_database_path() -> Path:
    configured = os.getenv("DATABASE_PATH", "").strip()

    if not configured:
        return DEFAULT_DATABASE

    path = Path(configured)

    if path.is_absolute():
        return path

    # Match app/config.py behavior: relative paths are inside the app package.
    return APP_ROOT / "app" / path


def is_valid_sqlite(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < len(SQLITE_HEADER):
        return False

    with path.open("rb") as handle:
        return handle.read(len(SQLITE_HEADER)) == SQLITE_HEADER


def main() -> int:
    destination = resolve_database_path()

    if is_valid_sqlite(destination):
        print(f"Runtime SQLite database ready: {destination}")
        return 0

    if not COMPRESSED_DATABASE.is_file():
        print(
            f"ERROR: compressed SQLite database not found: "
            f"{COMPRESSED_DATABASE}",
            file=sys.stderr,
        )
        return 1

    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(fd)
    temporary_path = Path(temporary_name)

    try:
        print(f"Preparing runtime SQLite database: {destination}")

        with gzip.open(COMPRESSED_DATABASE, "rb") as source:
            with temporary_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        if not is_valid_sqlite(temporary_path):
            raise RuntimeError(
                "Decompressed file does not have a valid SQLite header"
            )

        temporary_path.replace(destination)

        print(
            "Runtime SQLite database prepared "
            f"({destination.stat().st_size / 1024 / 1024:.2f} MiB)"
        )
        return 0

    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        print(f"ERROR: unable to prepare SQLite database: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
