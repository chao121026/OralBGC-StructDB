#!/usr/bin/env python3
"""Phase 1 public accession migration planner.

The default workflow is a non-destructive dry run that inventories source
records, assigns stable accession previews, and writes validation reports.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import posixpath
import re
import shutil
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from Bio import SeqIO


REGISTRY_COLUMNS = [
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

FILE_PLAN_COLUMNS = [
    "entity_type",
    "public_accession",
    "source_path",
    "public_path",
    "action",
    "content_change",
    "source_sha256",
    "public_sha256",
]

MISSING_COLUMNS = [
    "relationship",
    "child_entity",
    "child_original_identifier",
    "missing_parent_entity",
    "missing_parent_identifier",
]

COLLISION_COLUMNS = ["collision_type", "entity_type", "identifier", "first_value", "second_value"]
ROLLBACK_COLUMNS = ["public_path", "source_path", "action", "restore_action"]
TSV_PLAN_COLUMNS = ["source_tsv", "planned_public_columns", "planned_original_columns", "notes"]
LEGACY_COLUMNS = ["source", "field", "identifier", "token"]
LEGACY_CLASSIFICATION_COLUMNS = ["source", "field", "identifier", "token", "classification", "reason"]
GBK_INVENTORY_COLUMNS = [
    "archive_member",
    "basename",
    "normalized_source_identifier",
    "matched_bgc_original_identifier",
    "matched_bgc_accession",
    "match_method",
    "match_status",
    "size_bytes",
]
GBK_TRANSFORM_COLUMNS = [
    "source_member",
    "source_bgc_id",
    "public_bgc_accession",
    "target_member",
    "content_change_required",
    "planned_record_id",
    "planned_record_name",
    "planned_public_accession_field",
]
UNMATCHED_GBK_REVIEW_COLUMNS = [
    "archive_member",
    "basename",
    "record_id",
    "record_name",
    "record_description",
    "sequence_length",
    "feature_count",
    "region_number",
    "contig_identifier",
    "sample_identifier",
    "bin_identifier",
    "candidate_original_bgc_id",
    "candidate_existing_bgc_accession",
    "candidate_match_score",
    "candidate_match_reason",
    "classification",
    "exclusion_reason",
    "recommended_action",
    "evidence",
]
GBK_EXCLUSION_COLUMNS = ["archive_member", "classification", "reason", "evidence", "source_release", "review_status"]
PUBLIC_MAPPING_COLUMNS = [
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
]

ENTITY_PREFIX = {
    "MAG": "BGS-MAG",
    "BGC": "BGS-BGC",
    "PROTEIN": "BGS-PRT",
    "STRUCTURE": "BGS-STR",
}

LEGACY_TOKENS = ["metawrap_50_10_bins", "PHRC|", "region001", "contig_"]
APPROVED_PHASE1_REGISTRY_SHA256 = "75465047d4c4c0c4284db399e4e8b75b8a4e8cdd5636a078f6f2a0dc8b7760bf"
APPROVED_ENTITY_COUNTS = {"MAG": 583, "BGC": 1913, "GCF": 179, "PROTEIN": 22626, "STRUCTURE": 22622}
PUBLIC_PATH_COLUMNS = {
    "region_file",
    "model_cif",
    "bigscape_source_file",
    "region_file_ranking",
    "model_cif_ranking",
    "af3_job_name_ranking",
}


@dataclass(frozen=True)
class SourceRecord:
    entity_type: str
    original_identifier: str
    original_filename: str = ""
    parent_entity_type: str = ""
    parent_original_identifier: str = ""
    source_sample_id: str = ""
    source_bin_id: str = ""
    source_contig_id: str = ""
    source_region_id: str = ""
    source_path: str = ""


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=path.parent) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_sample_id(value: str) -> str:
    match = re.search(r"[A-Z]{2}_NA\d+_S\d+", value)
    return match.group(0) if match else ""


def extract_bin_id(value: str) -> str:
    match = re.search(r"bin\.\d+", value)
    return match.group(0) if match else ""


def normalize_region_number(value: str) -> str:
    if not value:
        return ""
    try:
        return f"region{int(value):03d}"
    except ValueError:
        return value


def discover_source_roots(source_root: Path) -> list[dict[str, str]]:
    candidates = [
        source_root,
        source_root / "tables",
        source_root / "antismash",
        source_root / "sequences",
        source_root / "structures",
        source_root / "checksums",
    ]
    rows = []
    for candidate in candidates:
        rows.append(
            {
                "path": candidate.as_posix(),
                "exists": "1" if candidate.exists() else "0",
                "kind": "directory" if candidate.is_dir() else "file" if candidate.exists() else "missing",
            }
        )
    return rows


def first_existing(root: Path, paths: list[str]) -> str:
    for rel in paths:
        if (root / rel).exists():
            return rel
    return ""


def find_cif_files(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    structures = root / "structures"
    if not structures.exists():
        return out
    for path in sorted(structures.glob("**/*.cif")):
        out.setdefault(path.stem, path.relative_to(root).as_posix())
    return out


def find_gbk_files(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for parent in [root / "antismash" / "region_gbk", root / "antismash"]:
        if not parent.exists():
            continue
        for path in sorted(parent.glob("**/*.gbk")):
            out.setdefault(path.name, path.relative_to(root).as_posix())
    return out


def load_source_records(source_root: Path) -> tuple[list[SourceRecord], list[dict[str, str]], dict[str, int]]:
    tables = source_root / "tables"
    mag_rows = read_tsv(tables / "MAG_summary.tsv")
    bgc_rows = read_tsv(tables / "BGC_summary.tsv")
    protein_rows = read_tsv(tables / "BGC_protein_summary.tsv")
    gcf_rows = read_tsv(tables / "BiGSCAPE_GCF_summary.tsv")
    if not any([mag_rows, bgc_rows, protein_rows, gcf_rows]):
        raise SystemExit(f"No supported source TSVs found under {tables}")

    gbk_files = find_gbk_files(source_root)
    cif_files = find_cif_files(source_root)
    records: list[SourceRecord] = []
    legacy_hits: list[dict[str, str]] = []

    for row in mag_rows:
        mag_id = row.get("mag_id") or row.get("genome_id") or ""
        if not mag_id:
            continue
        records.append(
            SourceRecord(
                entity_type="MAG",
                original_identifier=mag_id,
                source_sample_id=extract_sample_id(mag_id),
                source_bin_id=extract_bin_id(mag_id),
                source_path=first_existing(
                    source_root,
                    [
                        f"mags/{mag_id}.fna",
                        f"genomes/{mag_id}.fna",
                        f"sequences/{mag_id}.fna",
                    ],
                ),
            )
        )
        collect_legacy_hits("MAG_summary.tsv", row, mag_id, legacy_hits)

    for row in bgc_rows:
        bgc_id = row.get("bgc_id") or row.get("public_bgc_id", "").split("|")[-1]
        if not bgc_id:
            continue
        filename = row.get("region_basename", "")
        records.append(
            SourceRecord(
                entity_type="BGC",
                original_identifier=bgc_id,
                original_filename=filename,
                parent_entity_type="MAG",
                parent_original_identifier=row.get("genome_id", ""),
                source_sample_id=extract_sample_id(bgc_id),
                source_bin_id=extract_bin_id(bgc_id),
                source_contig_id=row.get("contig_id", ""),
                source_region_id=normalize_region_number(row.get("region_number", "")),
                source_path=gbk_files.get(filename, ""),
            )
        )
        gcf = row.get("bigscape_gcf_id_full_primary", "")
        if gcf:
            records.append(
                SourceRecord(
                    entity_type="BGC_GCF_LINK",
                    original_identifier=f"{bgc_id}\t{gcf}",
                    parent_entity_type="GCF",
                    parent_original_identifier=gcf,
                )
            )
        collect_legacy_hits("BGC_summary.tsv", row, bgc_id, legacy_hits)

    for row in protein_rows:
        query = row.get("query") or row.get("protein_id") or ""
        if not query:
            continue
        records.append(
            SourceRecord(
                entity_type="PROTEIN",
                original_identifier=query,
                parent_entity_type="BGC",
                parent_original_identifier=row.get("bgc_id", ""),
                source_sample_id=extract_sample_id(query),
                source_bin_id=extract_bin_id(query),
                source_contig_id=row.get("contig_id", ""),
                source_region_id=normalize_region_number(row.get("region_number", "")),
            )
        )
        if query in cif_files:
            records.append(
                SourceRecord(
                    entity_type="STRUCTURE",
                    original_identifier=query,
                    original_filename=f"{query}.cif",
                    parent_entity_type="PROTEIN",
                    parent_original_identifier=query,
                    source_sample_id=extract_sample_id(query),
                    source_bin_id=extract_bin_id(query),
                    source_contig_id=row.get("contig_id", ""),
                    source_region_id=normalize_region_number(row.get("region_number", "")),
                    source_path=cif_files[query],
                )
            )
        collect_legacy_hits("BGC_protein_summary.tsv", row, query, legacy_hits)

    for row in gcf_rows:
        gcf = row.get("bigscape_gcf_id_full_primary") or row.get("gcf_id") or ""
        if not gcf:
            continue
        records.append(
            SourceRecord(
                entity_type="GCF",
                original_identifier=gcf,
                source_path="",
            )
        )
        collect_legacy_hits("BiGSCAPE_GCF_summary.tsv", row, gcf, legacy_hits)

    counts = {
        "MAG": len({r.original_identifier for r in records if r.entity_type == "MAG"}),
        "BGC": len({r.original_identifier for r in records if r.entity_type == "BGC"}),
        "GCF": len({r.original_identifier for r in records if r.entity_type == "GCF"}),
        "PROTEIN": len({r.original_identifier for r in records if r.entity_type == "PROTEIN"}),
        "STRUCTURE": len({r.original_identifier for r in records if r.entity_type == "STRUCTURE"}),
    }
    return records, legacy_hits, counts


def collect_legacy_hits(source: str, row: dict[str, str], identifier: str, hits: list[dict[str, str]]) -> None:
    provenance_fields = {"mag_id", "genome_id", "bgc_id", "query", "region_basename", "contig_id", "bigscape_gcf_id_full_primary"}
    for field, value in row.items():
        if field in provenance_fields:
            continue
        for token in LEGACY_TOKENS:
            if token in value:
                hits.append({"source": source, "field": field, "identifier": identifier, "token": token})


def load_existing_registry(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    if not path.exists():
        return rows
    for row in read_tsv(path):
        key = (row["entity_type"], row["original_identifier"])
        rows[key] = {col: row.get(col, "") for col in REGISTRY_COLUMNS}
    return rows


def accession_number(entity_type: str, accession: str) -> int:
    if entity_type == "GCF":
        match = re.match(r"^BGS-GCF-[A-Z0-9]+-(\d{4})$", accession)
    else:
        match = re.match(rf"^{ENTITY_PREFIX[entity_type]}-(\d{{6}})$", accession)
    return int(match.group(1)) if match else 0


def gcf_cutoff_code(original_identifier: str) -> str:
    first = original_identifier.split("|", 1)[0]
    match = re.fullmatch(r"c(\d+)\.(\d+)", first)
    if not match:
        return re.sub(r"[^A-Za-z0-9]", "", first).upper() or "CXX"
    return f"C{match.group(1)}{match.group(2)}"


def allocate_accessions(
    records: list[SourceRecord],
    existing: dict[tuple[str, str], dict[str, str]],
    release_version: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    collisions: list[dict[str, str]] = []
    used_accessions: dict[str, tuple[str, str]] = {}
    next_numbers = {entity: 1 for entity in ["MAG", "BGC", "GCF", "PROTEIN", "STRUCTURE"]}
    for (entity_type, _), row in existing.items():
        if entity_type in next_numbers:
            next_numbers[entity_type] = max(next_numbers[entity_type], accession_number(entity_type, row["public_accession"]) + 1)
            previous = used_accessions.setdefault(row["public_accession"], (entity_type, row["original_identifier"]))
            if previous != (entity_type, row["original_identifier"]):
                collisions.append(
                    {
                        "collision_type": "duplicate_public_accession",
                        "entity_type": entity_type,
                        "identifier": row["public_accession"],
                        "first_value": previous[1],
                        "second_value": row["original_identifier"],
                    }
                )

    unique_records: dict[tuple[str, str], SourceRecord] = {}
    for record in records:
        if record.entity_type == "BGC_GCF_LINK":
            continue
        key = (record.entity_type, record.original_identifier)
        previous = unique_records.get(key)
        if previous and previous != record:
            collisions.append(
                {
                    "collision_type": "duplicate_original_identifier",
                    "entity_type": record.entity_type,
                    "identifier": record.original_identifier,
                    "first_value": previous.original_filename,
                    "second_value": record.original_filename,
                }
            )
        unique_records.setdefault(key, record)

    for key in sorted(unique_records, key=lambda item: (item[0], item[1].encode("utf-8"))):
        record = unique_records[key]
        existing_row = existing.get(key)
        if existing_row:
            row = dict(existing_row)
        else:
            row = blank_registry_row(record, release_version)
            if record.entity_type == "GCF":
                row["public_accession"] = f"BGS-GCF-{gcf_cutoff_code(record.original_identifier)}-{next_numbers['GCF']:04d}"
            else:
                row["public_accession"] = f"{ENTITY_PREFIX[record.entity_type]}-{next_numbers[record.entity_type]:06d}"
            next_numbers[record.entity_type] += 1
        row.update(
            {
                "source_collection": row.get("source_collection") or "PHRC",
                "original_filename": record.original_filename or row.get("original_filename", ""),
                "parent_original_identifier": record.parent_original_identifier or row.get("parent_original_identifier", ""),
                "source_sample_id": record.source_sample_id or row.get("source_sample_id", ""),
                "source_bin_id": record.source_bin_id or row.get("source_bin_id", ""),
                "source_contig_id": record.source_contig_id or row.get("source_contig_id", ""),
                "source_region_id": record.source_region_id or row.get("source_region_id", ""),
                "source_path": record.source_path or row.get("source_path", ""),
                "accession_status": row.get("accession_status") or "active",
            }
        )
        rows.append(row)
    return rows, collisions


def blank_registry_row(record: SourceRecord, release_version: str) -> dict[str, str]:
    row = {col: "" for col in REGISTRY_COLUMNS}
    row.update(
        {
            "entity_type": record.entity_type,
            "source_collection": "PHRC",
            "original_identifier": record.original_identifier,
            "original_filename": record.original_filename,
            "parent_original_identifier": record.parent_original_identifier,
            "source_sample_id": record.source_sample_id,
            "source_bin_id": record.source_bin_id,
            "source_contig_id": record.source_contig_id,
            "source_region_id": record.source_region_id,
            "release_version_created": release_version,
            "accession_status": "active",
            "source_path": record.source_path,
        }
    )
    return row


def fill_relationships(rows: list[dict[str, str]], records: list[SourceRecord]) -> list[dict[str, str]]:
    by_key = {(row["entity_type"], row["original_identifier"]): row for row in rows}
    missing: list[dict[str, str]] = []
    for record in records:
        if not record.parent_entity_type or not record.parent_original_identifier:
            continue
        if record.entity_type == "BGC_GCF_LINK":
            child = by_key.get(("BGC", record.original_identifier.split("\t", 1)[0]))
            parent = by_key.get(("GCF", record.parent_original_identifier))
            if not child or not parent:
                missing.append(
                    {
                        "relationship": "BGC -> primary GCF",
                        "child_entity": "BGC",
                        "child_original_identifier": record.original_identifier.split("\t", 1)[0],
                        "missing_parent_entity": "GCF",
                        "missing_parent_identifier": record.parent_original_identifier,
                    }
                )
            continue
        row = by_key.get((record.entity_type, record.original_identifier))
        parent = by_key.get((record.parent_entity_type, record.parent_original_identifier))
        if row and parent:
            row["parent_public_accession"] = parent["public_accession"]
        elif row:
            missing.append(
                {
                    "relationship": f"{record.entity_type} -> {record.parent_entity_type}",
                    "child_entity": record.entity_type,
                    "child_original_identifier": record.original_identifier,
                    "missing_parent_entity": record.parent_entity_type,
                    "missing_parent_identifier": record.parent_original_identifier,
                }
            )
    return missing


def public_relative_path(row: dict[str, str]) -> str:
    accession = row["public_accession"]
    entity = row["entity_type"]
    if entity == "MAG":
        return f"mags/{accession}.fna"
    if entity == "BGC":
        return f"antismash/region_gbk/{accession}.gbk"
    if entity == "PROTEIN":
        return f"sequences/proteins/{accession}.faa"
    if entity == "STRUCTURE":
        return f"structures/{accession}.cif"
    if entity == "GCF":
        return f"bigscape/gcfs/{accession}"
    return ""


def build_file_plan(source_root: Path, output_root: Path, rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    plan: list[dict[str, str]] = []
    collisions: list[dict[str, str]] = []
    seen_public: dict[str, str] = {}
    for row in rows:
        source_rel = row.get("source_path", "")
        public_rel = public_relative_path(row)
        row["public_path"] = public_rel
        if not source_rel:
            continue
        source_path = source_root / source_rel
        if not source_path.exists():
            continue
        source_hash = sha256(source_path)
        row["source_sha256"] = source_hash
        row["public_sha256"] = source_hash
        target_path = output_root / public_rel
        existing = seen_public.setdefault(public_rel, row["original_identifier"])
        if existing != row["original_identifier"]:
            collisions.append(
                {
                    "collision_type": "duplicate_public_path",
                    "entity_type": row["entity_type"],
                    "identifier": public_rel,
                    "first_value": existing,
                    "second_value": row["original_identifier"],
                }
            )
        if target_path.exists() and sha256(target_path) != source_hash:
            collisions.append(
                {
                    "collision_type": "existing_public_file_differs",
                    "entity_type": row["entity_type"],
                    "identifier": public_rel,
                    "first_value": source_hash,
                    "second_value": sha256(target_path),
                }
            )
        plan.append(
            {
                "entity_type": row["entity_type"],
                "public_accession": row["public_accession"],
                "source_path": source_rel,
                "public_path": public_rel,
                "action": "copy",
                "content_change": "none",
                "source_sha256": source_hash,
                "public_sha256": source_hash,
            }
        )
    return plan, collisions


def tsv_column_plan(source_root: Path) -> list[dict[str, str]]:
    candidates = {
        "MAG_summary.tsv": ("mag_accession", "original_mag_id"),
        "BGC_summary.tsv": ("bgc_accession,mag_accession,gcf_accession", "original_bgc_id,original_mag_id"),
        "BGC_protein_summary.tsv": ("protein_accession,bgc_accession,mag_accession,gcf_accession", "original_protein_id,original_bgc_id"),
        "AF3_model_summary.tsv": ("protein_accession,structure_accession", "original_protein_id,original_structure_filename"),
        "Foldseek_besthit_all.tsv": ("protein_accession", "original_protein_id"),
        "Foldseek_AF3QC_merged_all.tsv": ("protein_accession,structure_accession", "original_protein_id,original_structure_filename"),
        "PHRC_integrated_BGC_protein_structure_summary.tsv": ("protein_accession,bgc_accession,mag_accession,structure_accession", "original_protein_id,original_bgc_id"),
        "BiGSCAPE_BGC_to_GCF.tsv": ("bgc_accession,gcf_accession", "original_bgc_id,original_gcf_id"),
        "BiGSCAPE_GCF_summary.tsv": ("gcf_accession", "original_gcf_id"),
        "column_dictionary.tsv": ("public accession definitions", "source/original provenance definitions"),
    }
    rows = []
    for filename, (public_cols, original_cols) in candidates.items():
        path = source_root / "tables" / filename
        if path.exists():
            rows.append(
                {
                    "source_tsv": f"tables/{filename}",
                    "planned_public_columns": public_cols,
                    "planned_original_columns": original_cols,
                    "notes": "Phase 2 rewrites this table with public accession columns when --apply is used.",
                }
            )
    return rows


def is_unsafe_archive_member(member: str) -> bool:
    parts = member.split("/")
    return member.startswith("/") or any(part == ".." for part in parts)


def normalized_gbk_identifier(basename: str) -> str:
    stem = basename.removesuffix(".gbk")
    return stem.replace(".region", "_region")


def planned_bgc_structured_comment(
    public_accession: str,
    source_collection: str,
    original_identifier: str,
    original_filename: str,
) -> dict[str, dict[str, str]]:
    return {
        "PHRC_BGCStructDB": {
            "Public-Accession": public_accession,
            "Source-Collection": source_collection,
            "Original-BGC-Identifier": original_identifier,
            "Original-Filename": original_filename,
        }
    }


def build_gbk_archive_reports(
    source_root: Path,
    registry_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    archive = source_root / "antismash" / "region_gbk.tar.gz"
    bgcs_by_filename = {
        row["original_filename"]: row
        for row in registry_rows
        if row["entity_type"] == "BGC" and row.get("original_filename")
    }
    bgcs_by_parent_filename = {
        (row.get("parent_original_identifier", ""), row["original_filename"]): row
        for row in registry_rows
        if row["entity_type"] == "BGC" and row.get("original_filename")
    }
    known_mag_dirs = {row["original_identifier"] for row in registry_rows if row["entity_type"] == "MAG"}
    inventory: list[dict[str, str]] = []
    transform: list[dict[str, str]] = []
    matched_originals: set[str] = set()
    if not archive.exists():
        for row in sorted(bgcs_by_filename.values(), key=lambda item: item["public_accession"]):
            inventory.append(
                {
                    "archive_member": "",
                    "basename": row["original_filename"],
                    "normalized_source_identifier": normalized_gbk_identifier(row["original_filename"]),
                    "matched_bgc_original_identifier": row["original_identifier"],
                    "matched_bgc_accession": row["public_accession"],
                    "match_method": "original_filename",
                    "match_status": "bgc_without_gbk",
                    "size_bytes": "",
                }
            )
        return inventory, transform

    members = []
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile():
                members.append(member)
    basename_counts: dict[str, int] = {}
    for member in members:
        basename = posixpath.basename(member.name)
        basename_counts[basename] = basename_counts.get(basename, 0) + 1

    target_members: set[str] = set()
    for member in members:
        basename = posixpath.basename(member.name)
        dirname = posixpath.dirname(member.name).removeprefix("./")
        normalized = normalized_gbk_identifier(basename)
        row = bgcs_by_parent_filename.get((dirname, basename)) if dirname else bgcs_by_filename.get(basename)
        status = "matched"
        method = "parent_original_identifier+original_filename" if dirname and row else "original_filename"
        matched_original = row["original_identifier"] if row else ""
        matched_accession = row["public_accession"] if row else ""
        if is_unsafe_archive_member(member.name):
            status = "unsafe_path"
            method = ""
            row = None
            matched_original = ""
            matched_accession = ""
        elif dirname and dirname not in known_mag_dirs:
            status = "unexpected_directory"
            method = ""
            row = None
            matched_original = ""
            matched_accession = ""
        elif not basename.endswith(".gbk"):
            status = "non_gbk"
            method = ""
            row = None
            matched_original = ""
            matched_accession = ""
        elif basename_counts.get(basename, 0) > 1 and not dirname:
            status = "duplicate_basename"
            method = "original_filename"
        elif not row:
            status = "unmatched"
            method = "original_filename"

        inventory.append(
            {
                "archive_member": member.name,
                "basename": basename,
                "normalized_source_identifier": normalized,
                "matched_bgc_original_identifier": matched_original,
                "matched_bgc_accession": matched_accession,
                "match_method": method,
                "match_status": status,
                "size_bytes": str(member.size),
            }
        )
        if row and status == "matched":
            matched_originals.add(row["original_identifier"])
            target_member = f"{row['public_accession']}.gbk"
            target_status = "filename_collision" if target_member in target_members else "matched"
            target_members.add(target_member)
            if target_status == "filename_collision":
                inventory[-1]["match_status"] = target_status
            else:
                transform.append(
                    {
                        "source_member": member.name,
                        "source_bgc_id": row["original_identifier"],
                        "public_bgc_accession": row["public_accession"],
                        "target_member": target_member,
                        "content_change_required": "structured_comment_only",
                        "planned_record_id": "preserve_source_record_id",
                        "planned_record_name": "preserve_source_record_name",
                        "planned_public_accession_field": "StructuredComment.PHRC_BGCStructDB.Public-Accession",
                    }
                )

    for row in sorted(bgcs_by_filename.values(), key=lambda item: item["public_accession"]):
        if row["original_identifier"] in matched_originals:
            continue
        inventory.append(
            {
                "archive_member": "",
                "basename": row["original_filename"],
                "normalized_source_identifier": normalized_gbk_identifier(row["original_filename"]),
                "matched_bgc_original_identifier": row["original_identifier"],
                "matched_bgc_accession": row["public_accession"],
                "match_method": "original_filename",
                "match_status": "bgc_without_gbk",
                "size_bytes": "",
            }
        )
    return inventory, transform


def candidate_bgc_id(parent_mag: str, basename: str) -> str:
    stem = basename.removesuffix(".gbk")
    if ".region" in stem:
        contig, region_suffix = stem.rsplit(".region", 1)
        region = f"region{region_suffix}"
    else:
        contig = stem
        region = ""
    return f"{parent_mag.replace('__', '_')}_{contig}_{region}".rstrip("_")


def sample_from_identifier(value: str) -> str:
    match = re.search(r"[A-Z]+_NA\d+_S\d+", value)
    return match.group(0) if match else ""


def load_table_texts(source_root: Path) -> dict[str, str]:
    texts = {}
    for path in sorted((source_root / "tables").glob("*.tsv")):
        texts[path.name] = path.read_text(errors="ignore")
    return texts


def exact_source_hits(texts: dict[str, str], terms: list[str]) -> list[str]:
    hits = []
    for name, text in texts.items():
        matched = [term for term in terms if term and term in text]
        if matched:
            hits.append(f"{name}:{','.join(sorted(set(matched))[:4])}")
    return hits


def build_unmatched_gbk_review(
    source_root: Path,
    registry_rows: list[dict[str, str]],
    gbk_inventory: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    archive = source_root / "antismash" / "region_gbk.tar.gz"
    if not archive.exists():
        return [], []
    bgc_rows = [row for row in registry_rows if row["entity_type"] == "BGC"]
    mag_ids = {row["original_identifier"] for row in registry_rows if row["entity_type"] == "MAG"}
    by_accession = {row["public_accession"]: row for row in bgc_rows}
    matched_members = [row for row in gbk_inventory if row["match_status"] == "matched"]
    unmatched_members = [row for row in gbk_inventory if row["match_status"] in {"unmatched", "non_gbk", "unexpected_directory", "duplicate_basename", "filename_collision"}]
    table_texts = load_table_texts(source_root)
    sequence_to_accession: dict[str, str] = {}
    content_to_accession: dict[str, str] = {}
    with tarfile.open(archive, "r:gz") as tar:
        for row in matched_members:
            handle = tar.extractfile(row["archive_member"])
            if not handle:
                continue
            data = handle.read()
            content_to_accession[hashlib.sha256(data).hexdigest()] = row["matched_bgc_accession"]
            try:
                record = SeqIO.read(io.StringIO(data.decode()), "genbank")
            except Exception:
                continue
            sequence_to_accession[hashlib.sha256(str(record.seq).encode()).hexdigest()] = row["matched_bgc_accession"]

        review_rows: list[dict[str, str]] = []
        for row in unmatched_members:
            member = row["archive_member"]
            handle = tar.extractfile(member) if member else None
            parent_mag = posixpath.dirname(member).removeprefix("./") if member else ""
            basename = row["basename"]
            fallback = {
                "archive_member": member,
                "basename": basename,
                "record_id": "",
                "record_name": "",
                "record_description": "",
                "sequence_length": "",
                "feature_count": "",
                "region_number": "",
                "contig_identifier": basename.removesuffix(".gbk").split(".region", 1)[0],
                "sample_identifier": sample_from_identifier(member),
                "bin_identifier": extract_bin_id(parent_mag),
                "candidate_original_bgc_id": candidate_bgc_id(parent_mag, basename),
                "candidate_existing_bgc_accession": "",
                "candidate_match_score": "0.00",
                "candidate_match_reason": "not parsed",
                "classification": "unresolved",
                "exclusion_reason": "Unable to parse archive member for review.",
                "recommended_action": "manual_review_required",
                "evidence": f"archive_status={row['match_status']}",
            }
            if not handle:
                review_rows.append(fallback)
                continue
            data = handle.read()
            try:
                record = SeqIO.read(io.StringIO(data.decode()), "genbank")
            except Exception as exc:
                fallback["exclusion_reason"] = f"GenBank parse failed: {exc}"
                review_rows.append(fallback)
                continue
            region_features = [feature for feature in record.features if feature.type == "region"]
            protoclusters = [feature for feature in record.features if feature.type == "protocluster"]
            region_number = ""
            if region_features:
                region_number = (region_features[0].qualifiers.get("region_number") or [""])[0]
            if not region_number and ".region" in basename:
                region_number = basename.rsplit(".region", 1)[1].removesuffix(".gbk").lstrip("0") or "0"
            contig = basename.removesuffix(".gbk").split(".region", 1)[0]
            candidate = candidate_bgc_id(parent_mag, basename)
            terms = [basename, basename.removesuffix(".gbk"), contig, record.id, candidate, parent_mag]
            source_hits = exact_source_hits(table_texts, terms)
            content_hash = hashlib.sha256(data).hexdigest()
            seq_hash = hashlib.sha256(str(record.seq).encode()).hexdigest()
            existing = content_to_accession.get(content_hash) or sequence_to_accession.get(seq_hash, "")
            parent_in_registry = parent_mag in mag_ids
            true_region = bool(region_features or protoclusters)
            if not true_region:
                classification = "auxiliary_non_region_file"
                recommended = "exclude_from_public_archive"
                score = "0.10"
                reason = "Parsed GenBank lacks antiSMASH region/protocluster features."
            elif not parent_in_registry:
                classification = "excluded_parent_mag"
                recommended = "exclude_from_public_archive"
                score = "0.30"
                reason = "Parent MAG is not present in the public MAG registry."
            elif existing:
                classification = "duplicate_content"
                recommended = "exclude_from_public_archive"
                score = "1.00"
                reason = f"Exact {'content' if content_hash in content_to_accession else 'sequence'} checksum matches {existing}."
            else:
                classification = "curated_release_exclusion"
                recommended = "exclude_from_public_archive"
                score = "0.60"
                reason = "Archive-only true region record absent from BGC/protein/integrated public summary tables; retained as internal provenance."
            products = []
            for feature in region_features + protoclusters:
                products.extend(feature.qualifiers.get("product", []))
            review_rows.append(
                {
                    "archive_member": member,
                    "basename": basename,
                    "record_id": record.id,
                    "record_name": record.name,
                    "record_description": record.description,
                    "sequence_length": str(len(record.seq)),
                    "feature_count": str(len(record.features)),
                    "region_number": region_number,
                    "contig_identifier": contig,
                    "sample_identifier": sample_from_identifier(member),
                    "bin_identifier": extract_bin_id(parent_mag),
                    "candidate_original_bgc_id": candidate,
                    "candidate_existing_bgc_accession": existing,
                    "candidate_match_score": score,
                    "candidate_match_reason": reason,
                    "classification": classification,
                    "exclusion_reason": reason,
                    "recommended_action": recommended,
                    "evidence": "; ".join(
                        [
                            f"parent_mag={parent_mag}",
                            f"parent_mag_in_registry={parent_in_registry}",
                            f"region_features={len(region_features)}",
                            f"protoclusters={len(protoclusters)}",
                            f"products={ '|'.join(products[:4]) }",
                            f"source_hits={ '|'.join(source_hits[:8]) }",
                            "mag_qc_table=not_packaged",
                        ]
                    ),
                }
            )
    exclusion_rows = [
        {
            "archive_member": row["archive_member"],
            "classification": row["classification"],
            "reason": row["exclusion_reason"],
            "evidence": row["evidence"],
            "source_release": "PHRC_BGCStructDB_v1",
            "review_status": "approved_for_exclusion" if row["recommended_action"] == "exclude_from_public_archive" and row["classification"] != "unresolved" else "manual_review_required",
        }
        for row in review_rows
        if row["recommended_action"] in {"exclude_from_public_archive", "manual_review_required"}
    ]
    return review_rows, exclusion_rows


def load_approved_gbk_exclusions(path: Path | None) -> set[str]:
    if not path:
        return set()
    return {
        row["archive_member"]
        for row in read_tsv(path)
        if row.get("review_status") == "approved_for_exclusion"
    }


def unapproved_gbk_members(review_rows: list[dict[str, str]], approved: set[str]) -> list[str]:
    return [
        row["archive_member"]
        for row in review_rows
        if row["archive_member"] and row["archive_member"] not in approved
    ]


def classify_legacy_references(legacy_hits: list[dict[str, str]]) -> list[dict[str, str]]:
    allowed_fields = {
        "mag_id",
        "genome_id",
        "bgc_id",
        "query",
        "region_basename",
        "contig_id",
        "original_identifier",
        "original_filename",
        "source_sample_id",
        "source_bin_id",
        "source_contig_id",
        "source_region_id",
    }
    filename_fields = {"filename", "file", "path", "relative_path", "public_path", "archive_member"}
    rows = []
    for hit in legacy_hits:
        field = hit.get("field", "")
        if field in allowed_fields or field.startswith("original_") or field.startswith("source_"):
            classification = "allowed_provenance"
            reason = "legacy token appears in explicit provenance field"
        elif field in filename_fields or "url" in field.lower() or "display" in field.lower() or "accession" in field.lower():
            classification = "must_rewrite"
            reason = "legacy token appears in public filename, URL, display, or accession field"
        else:
            classification = "false_positive"
            reason = "not currently used as a public identifier field in Phase 1 scan"
        rows.append({**hit, "classification": classification, "reason": reason})
    return rows


def public_mapping_rows(registry_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{column: row.get(column, "") for column in PUBLIC_MAPPING_COLUMNS} for row in registry_rows]


def rollback_manifest(file_plan: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "public_path": row["public_path"],
            "source_path": row["source_path"],
            "action": row["action"],
            "restore_action": "remove public copy; original source remains unchanged",
        }
        for row in file_plan
    ]


def apply_file_plan(source_root: Path, output_root: Path, file_plan: list[dict[str, str]]) -> None:
    for row in file_plan:
        source_path = source_root / row["source_path"]
        target_path = output_root / row["public_path"]
        if not source_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists() and sha256(target_path) != row["source_sha256"]:
            raise SystemExit(f"Refusing to overwrite different existing file: {target_path}")
        if not target_path.exists():
            shutil.copy2(source_path, target_path)
        if sha256(target_path) != row["public_sha256"]:
            raise SystemExit(f"Checksum mismatch after copy: {target_path}")


def registry_hash(path: Path) -> str:
    return sha256(path)


def registry_rows_hash(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=REGISTRY_COLUMNS, delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return hashlib.sha256(buffer.getvalue().encode()).hexdigest()


def entity_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        entity: sum(1 for row in rows if row["entity_type"] == entity)
        for entity in ["MAG", "BGC", "GCF", "PROTEIN", "STRUCTURE"]
    }


def enforce_registry_immutability(existing: dict[tuple[str, str], dict[str, str]], rows: list[dict[str, str]]) -> None:
    for row in rows:
        key = (row["entity_type"], row["original_identifier"])
        previous = existing.get(key)
        if previous and previous.get("public_accession") != row["public_accession"]:
            raise SystemExit(
                "Existing registry maps original identifier differently: "
                f"{key} {previous.get('public_accession')} != {row['public_accession']}"
            )


def clean_partial_output(output_root: Path) -> Path:
    partial = output_root.with_name(output_root.name + ".partial")
    if output_root.exists():
        raise SystemExit(f"Output root already exists; refusing to overwrite: {output_root}")
    if partial.exists():
        shutil.rmtree(partial)
    partial.mkdir(parents=True)
    return partial


def promote_partial_output(partial: Path, output_root: Path) -> None:
    if output_root.exists():
        raise SystemExit(f"Output root appeared before promotion: {output_root}")
    partial.replace(output_root)


def row_maps(rows: list[dict[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
    return {
        entity: {row["original_identifier"]: row for row in rows if row["entity_type"] == entity}
        for entity in ["MAG", "BGC", "GCF", "PROTEIN", "STRUCTURE"]
    }


def copy_release_cifs(source_root: Path, output_root: Path, file_plan: list[dict[str, str]]) -> int:
    count = 0
    for row in sorted(file_plan, key=lambda item: item["public_accession"]):
        if row["entity_type"] != "STRUCTURE":
            continue
        source = source_root / row["source_path"]
        target = output_root / row["public_path"]
        if not source.exists():
            raise SystemExit(f"Missing source CIF: {source}")
        if sha256(source) != row["source_sha256"]:
            raise SystemExit(f"Source CIF checksum mismatch: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(source, temp)
        if sha256(temp) != row["source_sha256"]:
            raise SystemExit(f"Copied CIF checksum mismatch: {target}")
        temp.replace(target)
        count += 1
    return count


def merge_bgc_structured_comment(record, registry_row: dict[str, str], release_version: str) -> None:
    structured = dict(record.annotations.get("structured_comment", {}))
    structured["PHRC_BGCStructDB"] = {
        "Public-Accession": registry_row["public_accession"],
        "Source-Collection": registry_row["source_collection"],
        "Original-BGC-Identifier": registry_row["original_identifier"],
        "Original-Filename": registry_row["original_filename"],
        "Release-Version": release_version,
    }
    record.annotations["structured_comment"] = structured


def deterministic_tar_gz(path: Path, members: list[tuple[str, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(mode="w", fileobj=gz) as tar:
                for name, data in sorted(members, key=lambda item: item[0]):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    tar.addfile(info, io.BytesIO(data))


def transform_gbk_archive(
    source_root: Path,
    output_root: Path,
    registry_rows: list[dict[str, str]],
    gbk_transform: list[dict[str, str]],
    release_version: str,
) -> int:
    by_bgc = {row["original_identifier"]: row for row in registry_rows if row["entity_type"] == "BGC"}
    archive = source_root / "antismash" / "region_gbk.tar.gz"
    members: list[tuple[str, bytes]] = []
    with tarfile.open(archive, "r:gz") as tar:
        for plan in sorted(gbk_transform, key=lambda item: item["public_bgc_accession"]):
            source_member = plan["source_member"]
            if is_unsafe_archive_member(source_member):
                raise SystemExit(f"Unsafe GBK archive member: {source_member}")
            extracted = tar.extractfile(source_member)
            if not extracted:
                raise SystemExit(f"Missing GBK member: {source_member}")
            data = extracted.read()
            original = SeqIO.read(io.StringIO(data.decode()), "genbank")
            before_seq = str(original.seq)
            before_features = len(original.features)
            registry_row = by_bgc[plan["source_bgc_id"]]
            merge_bgc_structured_comment(original, registry_row, release_version)
            handle = io.StringIO()
            SeqIO.write(original, handle, "genbank")
            out_data = handle.getvalue().encode()
            reparsed = SeqIO.read(io.StringIO(out_data.decode()), "genbank")
            if str(reparsed.seq) != before_seq or len(reparsed.features) != before_features:
                raise SystemExit(f"GBK transformation changed sequence/features: {source_member}")
            members.append((plan["target_member"], out_data))
    deterministic_tar_gz(output_root / "antismash" / f"BGS_BGC_GBK_{release_version}.tar.gz", members)
    return len(members)


def parse_fasta(path: Path) -> list[tuple[str, str, str]]:
    records = []
    header = ""
    seq_parts: list[str] = []
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            if header:
                records.append((header.split()[0], header, "".join(seq_parts)))
            header = line[1:].strip()
            seq_parts = []
        else:
            seq_parts.append(line.strip())
    if header:
        records.append((header.split()[0], header, "".join(seq_parts)))
    return records


def write_accession_fasta(source_root: Path, output_root: Path, rows: list[dict[str, str]]) -> int:
    maps = row_maps(rows)
    source = source_root / "sequences" / "BGC_proteins.faa"
    records = parse_fasta(source)
    out_lines = []
    seen = set()
    for original_id, _header, sequence in records:
        protein = maps["PROTEIN"].get(original_id)
        if not protein:
            raise SystemExit(f"Protein FASTA record lacks accession: {original_id}")
        accession = protein["public_accession"]
        if accession in seen:
            raise SystemExit(f"Duplicate protein FASTA accession: {accession}")
        if not sequence:
            raise SystemExit(f"Blank protein FASTA sequence: {original_id}")
        seen.add(accession)
        out_lines.append(f">{accession} source_collection={protein['source_collection']} bgc={protein['parent_public_accession']}")
        out_lines.append(sequence)
    target = output_root / "sequences" / "BGS_BGC_proteins_v1.0.faa"
    write_text_atomic(target, "\n".join(out_lines) + "\n")
    return len(records)


def gcf_original_from_assignment(row: dict[str, str]) -> str:
    if row.get("bigscape_gcf_id_full_primary"):
        return row["bigscape_gcf_id_full_primary"]
    if row.get("bigscape_gcf_id_full"):
        return row["bigscape_gcf_id_full"]
    cutoff = row.get("bigscape_cutoff", "")
    family = row.get("bigscape_gcf_id", "")
    klass = row.get("bigscape_class", "")
    if cutoff and family and klass:
        return f"c{cutoff}|{klass}|{family}"
    return ""


def transform_public_row(row: dict[str, str], maps: dict[str, dict[str, dict[str, str]]], filename_to_bgc: dict[str, dict[str, str]]) -> dict[str, str]:
    mag_original = row.get("mag_id") or row.get("genome_id", "")
    bgc_original = row.get("bgc_id", "")
    protein_original = row.get("query", "")
    if not bgc_original:
        raw = row.get("bigscape_bgc_key") or row.get("bigscape_bgc_raw", "")
        bgc = filename_to_bgc.get(raw)
        bgc_original = bgc["original_identifier"] if bgc else ""
    gcf_original = gcf_original_from_assignment(row)
    structure = maps["STRUCTURE"].get(protein_original) if protein_original else None
    out = {
        "mag_accession": maps["MAG"].get(mag_original, {}).get("public_accession", ""),
        "bgc_accession": maps["BGC"].get(bgc_original, {}).get("public_accession", ""),
        "primary_gcf_accession": maps["GCF"].get(gcf_original, {}).get("public_accession", "") if gcf_original else "",
        "protein_accession": maps["PROTEIN"].get(protein_original, {}).get("public_accession", ""),
        "structure_accession": structure["public_accession"] if structure else "",
        "source_collection": "PHRC",
        "original_mag_id": mag_original,
        "original_bgc_id": bgc_original,
        "original_protein_id": protein_original,
        "original_structure_filename": structure["original_filename"] if structure else "",
    }
    for key, value in row.items():
        if key in PUBLIC_PATH_COLUMNS:
            continue
        if isinstance(value, str) and (value.startswith("/Users/") or value.startswith("/scratch/")):
            continue
        out[key] = value
    return out


def rewrite_public_tsvs(source_root: Path, output_root: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    maps = row_maps(rows)
    filename_to_bgc = {
        bgc["original_filename"].removesuffix(".gbk"): bgc
        for bgc in rows
        if bgc["entity_type"] == "BGC" and bgc.get("original_filename")
    }
    rewritten = []
    for source in sorted((source_root / "tables").glob("*.tsv")):
        if "internal_priority" in source.name or source.name == "drug_discovery_ranked_candidates.tsv":
            continue
        source_rows = read_tsv(source)
        if not source_rows:
            continue
        out_rows = [transform_public_row(row, maps, filename_to_bgc) for row in source_rows]
        fields = list(out_rows[0])
        target = output_root / "metadata" / "tables" / source.name
        write_tsv(target, out_rows, fields)
        rewritten.append({"table": source.name, "rows": str(len(out_rows)), "path": target.relative_to(output_root).as_posix()})
    return rewritten


def archive_release_structures(output_root: Path, file_plan: list[dict[str, str]], release_version: str) -> dict[str, int]:
    buckets = {"short": [], "medium": [], "long": []}
    for row in sorted(file_plan, key=lambda item: item["public_accession"]):
        if row["entity_type"] != "STRUCTURE":
            continue
        source_rel = row["source_path"]
        bucket = "short" if "short" in source_rel else "medium" if "medium" in source_rel else "long"
        path = output_root / row["public_path"]
        buckets[bucket].append((Path(row["public_path"]).name, path.read_bytes()))
    counts = {}
    for bucket, members in buckets.items():
        archive = output_root / "structures" / f"BGS_structures_{bucket}_{release_version}.tar.gz"
        deterministic_tar_gz(archive, members)
        counts[archive.relative_to(output_root).as_posix()] = len(members)
    return counts


def file_manifest_row(output_root: Path, rel: str, content_type: str, entity_type: str, record_count: int, release_version: str) -> dict[str, str]:
    path = output_root / rel
    return {
        "public_filename": rel,
        "content_type": content_type,
        "entity_type": entity_type,
        "record_count": str(record_count),
        "size_bytes": str(path.stat().st_size),
        "sha256": sha256(path),
        "release_version": release_version,
        "availability": "public",
    }


def write_manifests(output_root: Path, release_version: str, rows: list[dict[str, str]], fasta_count: int, gbk_count: int, structure_archive_counts: dict[str, int], tsv_rows: list[dict[str, str]]) -> None:
    manifest = [
        file_manifest_row(output_root, "metadata/BGS_public_accession_mapping.tsv", "tsv", "accession_mapping", len(rows), release_version),
        file_manifest_row(output_root, f"sequences/BGS_BGC_proteins_v1.0.faa", "fasta", "PROTEIN", fasta_count, release_version),
        file_manifest_row(output_root, f"antismash/BGS_BGC_GBK_{release_version}.tar.gz", "tar.gz", "BGC", gbk_count, release_version),
    ]
    for rel, count in sorted(structure_archive_counts.items()):
        manifest.append(file_manifest_row(output_root, rel, "tar.gz", "STRUCTURE", count, release_version))
    for table in tsv_rows:
        manifest.append(file_manifest_row(output_root, table["path"], "tsv", "table", int(table["rows"]), release_version))
    write_tsv(output_root / "manifests" / "public_file_manifest.tsv", manifest, ["public_filename", "content_type", "entity_type", "record_count", "size_bytes", "sha256", "release_version", "availability"])
    checksum_paths = [row["public_filename"] for row in manifest]
    sha_lines = []
    md5_lines = []
    for rel in sorted(checksum_paths):
        path = output_root / rel
        sha_lines.append(f"{sha256(path)}  {rel}")
        md5 = hashlib.md5(path.read_bytes()).hexdigest()
        md5_lines.append(f"{md5}  {rel}")
    write_text_atomic(output_root / "manifests" / "sha256sums.txt", "\n".join(sha_lines) + "\n")
    write_text_atomic(output_root / "manifests" / "md5sums.txt", "\n".join(md5_lines) + "\n")


def validate_release_tree(output_root: Path, rows: list[dict[str, str]], fasta_count: int, gbk_count: int, cif_count: int) -> None:
    counts = entity_counts(rows)
    if counts == APPROVED_ENTITY_COUNTS:
        expected = APPROVED_ENTITY_COUNTS
        if fasta_count != expected["PROTEIN"] or gbk_count != expected["BGC"] or cif_count != expected["STRUCTURE"]:
            raise SystemExit("Release output counts do not match approved Phase 1 counts")
    with tarfile.open(output_root / "antismash" / "BGS_BGC_GBK_v1.0.tar.gz", "r:gz") as tar:
        names = tar.getnames()
        if len(names) != gbk_count or len(names) != len(set(names)):
            raise SystemExit("GBK archive member count/uniqueness validation failed")
        if any(not re.fullmatch(r"BGS-BGC-\d{6}\.gbk", name) for name in names):
            raise SystemExit("GBK archive contains non-accession member names")
    if not (output_root / "manifests" / "public_file_manifest.tsv").exists():
        raise SystemExit("Missing public file manifest")


def build_release_tree(
    source_root: Path,
    output_root: Path,
    registry: Path,
    rows: list[dict[str, str]],
    file_plan: list[dict[str, str]],
    gbk_transform: list[dict[str, str]],
    gbk_exclusion_manifest: list[dict[str, str]],
    release_version: str,
) -> Path:
    partial = clean_partial_output(output_root)
    try:
        for dirname in ["metadata", "sequences", "structures", "antismash", "bigscape", "foldseek", "documentation", "manifests", "provenance"]:
            (partial / dirname).mkdir(parents=True, exist_ok=True)
        write_tsv(partial / "metadata" / "BGS_public_accession_mapping.tsv", public_mapping_rows(rows), PUBLIC_MAPPING_COLUMNS)
        write_tsv(partial / "provenance" / "internal_accession_registry.tsv", rows, REGISTRY_COLUMNS)
        write_tsv(partial / "provenance" / "gbk_exclusion_manifest.tsv", gbk_exclusion_manifest, GBK_EXCLUSION_COLUMNS)
        cif_count = copy_release_cifs(source_root, partial, file_plan)
        gbk_count = transform_gbk_archive(source_root, partial, rows, gbk_transform, release_version)
        fasta_count = write_accession_fasta(source_root, partial, rows)
        tsv_rows = rewrite_public_tsvs(source_root, partial, rows)
        structure_archives = archive_release_structures(partial, file_plan, release_version)
        write_manifests(partial, release_version, rows, fasta_count, gbk_count, structure_archives, tsv_rows)
        write_tsv(
            partial / "provenance" / "internal_migration_log.tsv",
            [
                {"key": "release_version", "value": release_version},
                {"key": "cif_files", "value": str(cif_count)},
                {"key": "gbk_members", "value": str(gbk_count)},
                {"key": "fasta_records", "value": str(fasta_count)},
                {"key": "excluded_gbks", "value": str(len(gbk_exclusion_manifest))},
            ],
            ["key", "value"],
        )
        validate_release_tree(partial, rows, fasta_count, gbk_count, cif_count)
        persist_registry(registry, rows)
        if entity_counts(rows) == APPROVED_ENTITY_COUNTS and registry_hash(registry) != APPROVED_PHASE1_REGISTRY_SHA256:
            raise SystemExit("Frozen registry hash does not match approved Phase 1 hash")
        promote_partial_output(partial, output_root)
    except Exception:
        if partial.exists():
            shutil.rmtree(partial)
        raise
    return output_root


def build_summary(
    records: list[SourceRecord],
    rows: list[dict[str, str]],
    file_plan: list[dict[str, str]],
    tsv_plan: list[dict[str, str]],
    collisions: list[dict[str, str]],
    missing: list[dict[str, str]],
    gbk_inventory: list[dict[str, str]],
    gbk_transform: list[dict[str, str]],
    unmatched_gbk_review: list[dict[str, str]],
    gbk_exclusion_manifest: list[dict[str, str]],
) -> dict[str, object]:
    gbk_status_counts: dict[str, int] = {}
    for row in gbk_inventory:
        status = row["match_status"]
        gbk_status_counts[status] = gbk_status_counts.get(status, 0) + 1
    return {
        "records_mapped": {
            entity: sum(1 for row in rows if row["entity_type"] == entity)
            for entity in ["MAG", "BGC", "GCF", "PROTEIN", "STRUCTURE"]
        },
        "source_records_seen": {
            entity: len({record.original_identifier for record in records if record.entity_type == entity})
            for entity in ["MAG", "BGC", "GCF", "PROTEIN", "STRUCTURE"]
        },
        "files_to_copy": len(file_plan),
        "files_to_rename": 0,
        "tsvs_to_rewrite": len(tsv_plan),
        "collisions": len(collisions),
        "missing_parents": len(missing),
        "unresolved_references": len(missing),
        "gbk_archive_members": sum(1 for row in gbk_inventory if row["archive_member"]),
        "gbk_transform_members": len(gbk_transform),
        "approved_excluded_gbks": sum(1 for row in gbk_exclusion_manifest if row["review_status"] == "approved_for_exclusion"),
        "unresolved_gbks": sum(1 for row in gbk_exclusion_manifest if row["review_status"] != "approved_for_exclusion"),
        "gbk_status_counts": gbk_status_counts,
    }


def write_reports(
    artifact_root: Path,
    rows: list[dict[str, str]],
    file_plan: list[dict[str, str]],
    tsv_plan: list[dict[str, str]],
    collisions: list[dict[str, str]],
    missing: list[dict[str, str]],
    legacy_hits: list[dict[str, str]],
    legacy_classification: list[dict[str, str]],
    gbk_inventory: list[dict[str, str]],
    gbk_transform: list[dict[str, str]],
    unmatched_gbk_review: list[dict[str, str]],
    gbk_exclusion_manifest: list[dict[str, str]],
    summary: dict[str, object],
    source_roots: list[dict[str, str]],
) -> None:
    write_tsv(artifact_root / "accession_registry_preview.tsv", rows, REGISTRY_COLUMNS)
    write_tsv(artifact_root / "internal_accession_registry.tsv", rows, REGISTRY_COLUMNS)
    write_tsv(artifact_root / "public_accession_mapping.tsv", public_mapping_rows(rows), PUBLIC_MAPPING_COLUMNS)
    write_tsv(artifact_root / "file_rename_plan.tsv", file_plan, FILE_PLAN_COLUMNS)
    write_tsv(artifact_root / "tsv_column_plan.tsv", tsv_plan, TSV_PLAN_COLUMNS)
    write_tsv(artifact_root / "collision_report.tsv", collisions, COLLISION_COLUMNS)
    write_tsv(artifact_root / "missing_reference_report.tsv", missing, MISSING_COLUMNS)
    write_tsv(artifact_root / "legacy_reference_report.tsv", legacy_hits, LEGACY_COLUMNS)
    write_tsv(artifact_root / "legacy_reference_classification.tsv", legacy_classification, LEGACY_CLASSIFICATION_COLUMNS)
    write_tsv(artifact_root / "gbk_archive_inventory.tsv", gbk_inventory, GBK_INVENTORY_COLUMNS)
    write_tsv(artifact_root / "gbk_transform_plan.tsv", gbk_transform, GBK_TRANSFORM_COLUMNS)
    write_tsv(artifact_root / "unmatched_gbk_review.tsv", unmatched_gbk_review, UNMATCHED_GBK_REVIEW_COLUMNS)
    write_tsv(artifact_root / "gbk_exclusion_manifest.tsv", gbk_exclusion_manifest, GBK_EXCLUSION_COLUMNS)
    write_tsv(artifact_root / "rollback_manifest.tsv", rollback_manifest(file_plan), ROLLBACK_COLUMNS)
    write_tsv(artifact_root / "source_root_inventory.tsv", source_roots, ["path", "exists", "kind"])
    write_text_atomic(artifact_root / "count_summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")


def persist_registry(path: Path, rows: list[dict[str, str]]) -> None:
    write_tsv(path, rows, REGISTRY_COLUMNS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or apply stable BGS public accession migration.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--gbk-exclusion-manifest", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    registry = args.registry.resolve()
    artifact_root = output_root / "artifacts" / "accession_migration"

    records, legacy_hits, _ = load_source_records(source_root)
    existing_registry = load_existing_registry(registry)
    rows, collisions = allocate_accessions(records, existing_registry, args.release_version)
    enforce_registry_immutability(existing_registry, rows)
    missing = fill_relationships(rows, records)
    file_plan, file_collisions = build_file_plan(source_root, output_root, rows)
    collisions.extend(file_collisions)
    tsv_plan = tsv_column_plan(source_root)
    gbk_inventory, gbk_transform = build_gbk_archive_reports(source_root, rows)
    unmatched_gbk_review, gbk_exclusion_manifest = build_unmatched_gbk_review(source_root, rows, gbk_inventory)
    legacy_classification = classify_legacy_references(legacy_hits)
    summary = build_summary(records, rows, file_plan, tsv_plan, collisions, missing, gbk_inventory, gbk_transform, unmatched_gbk_review, gbk_exclusion_manifest)
    if args.dry_run:
        write_reports(
            artifact_root,
            rows,
            file_plan,
            tsv_plan,
            collisions,
            missing,
            legacy_hits,
            legacy_classification,
            gbk_inventory,
            gbk_transform,
            unmatched_gbk_review,
            gbk_exclusion_manifest,
            summary,
            discover_source_roots(source_root),
        )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if collisions:
        print(f"Found {len(collisions)} collisions; see {artifact_root / 'collision_report.tsv'}", file=sys.stderr)
    if missing:
        print(f"Found {len(missing)} missing parent relationships; see {artifact_root / 'missing_reference_report.tsv'}", file=sys.stderr)
    if args.apply:
        if entity_counts(rows) == APPROVED_ENTITY_COUNTS and registry_rows_hash(rows) != APPROVED_PHASE1_REGISTRY_SHA256:
            print("Registry preview hash does not match approved Phase 1 hash.", file=sys.stderr)
            return 2
        unapproved = unapproved_gbk_members(unmatched_gbk_review, load_approved_gbk_exclusions(args.gbk_exclusion_manifest))
        if unapproved:
            print(
                f"Found {len(unapproved)} unapproved extra GBK archive members; provide --gbk-exclusion-manifest after review.",
                file=sys.stderr,
            )
            return 2
        if collisions or missing:
            return 2
        build_release_tree(source_root, output_root, registry, rows, file_plan, gbk_transform, gbk_exclusion_manifest, args.release_version)
    return 0 if not (args.apply and (collisions or missing)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
