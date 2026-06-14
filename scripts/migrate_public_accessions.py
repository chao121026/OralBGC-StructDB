#!/usr/bin/env python3
"""Phase 1 public accession migration planner.

The default workflow is a non-destructive dry run that inventories source
records, assigns stable accession previews, and writes validation reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


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

ENTITY_PREFIX = {
    "MAG": "BGS-MAG",
    "BGC": "BGS-BGC",
    "PROTEIN": "BGS-PRT",
    "STRUCTURE": "BGS-STR",
}

LEGACY_TOKENS = ["metawrap_50_10_bins", "PHRC|", "region001", "contig_"]


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
                    "notes": "Phase 3 rewrite candidate; Phase 1 dry run leaves source unchanged.",
                }
            )
    return rows


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


def build_summary(records: list[SourceRecord], rows: list[dict[str, str]], file_plan: list[dict[str, str]], collisions: list[dict[str, str]], missing: list[dict[str, str]]) -> dict[str, object]:
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
        "tsvs_to_rewrite": "deferred_to_phase_3",
        "collisions": len(collisions),
        "missing_parents": len(missing),
        "unresolved_references": len(missing),
    }


def write_reports(
    artifact_root: Path,
    rows: list[dict[str, str]],
    file_plan: list[dict[str, str]],
    tsv_plan: list[dict[str, str]],
    collisions: list[dict[str, str]],
    missing: list[dict[str, str]],
    legacy_hits: list[dict[str, str]],
    summary: dict[str, object],
    source_roots: list[dict[str, str]],
) -> None:
    write_tsv(artifact_root / "accession_registry_preview.tsv", rows, REGISTRY_COLUMNS)
    write_tsv(artifact_root / "file_rename_plan.tsv", file_plan, FILE_PLAN_COLUMNS)
    write_tsv(artifact_root / "tsv_column_plan.tsv", tsv_plan, TSV_PLAN_COLUMNS)
    write_tsv(artifact_root / "collision_report.tsv", collisions, COLLISION_COLUMNS)
    write_tsv(artifact_root / "missing_reference_report.tsv", missing, MISSING_COLUMNS)
    write_tsv(artifact_root / "legacy_reference_report.tsv", legacy_hits, LEGACY_COLUMNS)
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
    rows, collisions = allocate_accessions(records, load_existing_registry(registry), args.release_version)
    missing = fill_relationships(rows, records)
    file_plan, file_collisions = build_file_plan(source_root, output_root, rows)
    collisions.extend(file_collisions)
    tsv_plan = tsv_column_plan(source_root)
    summary = build_summary(records, rows, file_plan, collisions, missing)
    write_reports(
        artifact_root,
        rows,
        file_plan,
        tsv_plan,
        collisions,
        missing,
        legacy_hits,
        summary,
        discover_source_roots(source_root),
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if collisions:
        print(f"Found {len(collisions)} collisions; see {artifact_root / 'collision_report.tsv'}", file=sys.stderr)
    if missing:
        print(f"Found {len(missing)} missing parent relationships; see {artifact_root / 'missing_reference_report.tsv'}", file=sys.stderr)
    if args.apply:
        if collisions or missing:
            return 2
        apply_file_plan(source_root, output_root, file_plan)
        persist_registry(registry, rows)
        write_text_atomic(artifact_root / "migration.log", "apply completed\n")
    return 0 if not (args.apply and (collisions or missing)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
