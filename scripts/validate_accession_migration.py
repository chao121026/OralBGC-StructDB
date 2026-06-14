#!/usr/bin/env python3
"""Validate a BGS public accession registry and release tree."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path


REQUIRED_COLUMNS = [
    "entity_type",
    "public_accession",
    "source_collection",
    "original_identifier",
    "original_filename",
    "parent_public_accession",
    "parent_original_identifier",
    "source_sample_id",
    "source_bin_id",
    "source_contig_id",
    "source_region_id",
    "release_version_created",
    "accession_status",
    "source_path",
    "public_path",
    "source_sha256",
    "public_sha256",
]

ACCESSION_PATTERNS = {
    "MAG": re.compile(r"^BGS-MAG-\d{6}$"),
    "BGC": re.compile(r"^BGS-BGC-\d{6}$"),
    "PROTEIN": re.compile(r"^BGS-PRT-\d{6}$"),
    "STRUCTURE": re.compile(r"^BGS-STR-\d{6}$"),
    "GCF": re.compile(r"^BGS-GCF-[A-Z0-9]+-\d{4}$"),
}


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames or [], list(reader)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_error(errors: list[dict[str, str]], code: str, detail: str) -> None:
    errors.append({"code": code, "detail": detail})


def validate_registry(registry: Path, release_root: Path) -> dict[str, object]:
    fieldnames, rows = read_tsv(registry)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        add_error(errors, "missing_columns", ",".join(missing))

    by_accession: dict[str, dict[str, str]] = {}
    by_entity_original: dict[tuple[str, str], dict[str, str]] = {}
    by_public_path: dict[str, str] = {}
    for row in rows:
        entity = row.get("entity_type", "")
        accession = row.get("public_accession", "")
        original = row.get("original_identifier", "")
        pattern = ACCESSION_PATTERNS.get(entity)
        if not pattern:
            add_error(errors, "unknown_entity_type", entity)
        elif not pattern.fullmatch(accession):
            add_error(errors, "invalid_accession", f"{entity}:{accession}")

        existing_accession = by_accession.setdefault(accession, row)
        if existing_accession is not row:
            add_error(errors, "duplicate_public_accession", accession)
        key = (entity, original)
        existing_original = by_entity_original.setdefault(key, row)
        if existing_original is not row:
            add_error(errors, "duplicate_original_identifier", f"{entity}:{original}")

        public_path = row.get("public_path", "")
        if public_path:
            previous = by_public_path.setdefault(public_path, accession)
            if previous != accession:
                add_error(errors, "duplicate_public_path", public_path)
            path = release_root / public_path
            expected = row.get("public_sha256", "")
            if path.exists() and expected and sha256(path) != expected:
                add_error(errors, "public_checksum_mismatch", public_path)
            elif not path.exists() and expected:
                warnings.append({"code": "public_file_missing", "detail": public_path})

    for row in rows:
        parent = row.get("parent_public_accession", "")
        if parent and parent not in by_accession:
            add_error(errors, "missing_parent_accession", f"{row.get('public_accession')} -> {parent}")

    return {
        "registry": registry.as_posix(),
        "release_root": release_root.as_posix(),
        "records": len(rows),
        "errors": len(errors),
        "warnings": len(warnings),
        "error_details": errors[:50],
        "warning_details": warnings[:50],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BGS accession registry and release outputs.")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--release-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_registry(args.registry.resolve(), args.release_root.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"]:
        print(f"Validation failed with {report['errors']} errors", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
