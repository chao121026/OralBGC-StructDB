#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PUBLIC_TABLES = {
    "MAG_summary.tsv": "mag_summary",
    "BGC_summary.tsv": "bgc_summary",
    "BGC_protein_summary.tsv": "bgc_protein_summary",
    "BiGSCAPE_GCF_summary.tsv": "bigscape_gcf_summary",
    "BiGSCAPE_BGC_to_GCF.tsv": "bigscape_bgc_to_gcf",
    "AF3_model_summary.tsv": "af3_model_summary",
    "Foldseek_besthit_all.tsv": "foldseek_besthit_all",
    "Foldseek_AF3QC_merged_all.tsv": "foldseek_af3qc_merged_all",
    "PHRC_integrated_BGC_protein_structure_summary.tsv": "integrated_summary",
    "column_dictionary.tsv": "column_dictionary",
}
ACCESSION_ALIASES = {
    "mag_accession": "public_mag_id",
    "bgc_accession": "public_bgc_id",
    "primary_gcf_accession": "public_gcf_id",
    "protein_accession": "public_protein_id",
    "structure_accession": "public_structure_id",
}
SECONDARY_ACCESSION_ALIASES = {
    "primary_gcf_accession": "gcf_accession",
}
SENSITIVE_COLUMNS = {
    "drug_discovery_priority_score",
    "priority_class",
    "database_candidate_tier",
}
PATH_COLUMNS = {
    "region_file",
    "model_cif",
    "bigscape_source_file",
    "region_file_ranking",
    "model_cif_ranking",
    "af3_job_name_ranking",
}
EXCLUDED_FILES = {
    "PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv",
    "drug_discovery_ranked_candidates.tsv",
    "candidate_peptides.faa",
    "high_priority_candidate_models.tar.gz",
}
LEGACY_ALLOWLIST = [
    ("tables/MAG_summary.tsv", "Tables", "MAG summary table"),
    ("tables/BGC_summary.tsv", "Tables", "BGC summary table"),
    ("tables/BGC_protein_summary.tsv", "Tables", "BGC protein summary table"),
    ("tables/BiGSCAPE_GCF_summary.tsv", "Tables", "BiG-SCAPE primary c0.3 GCF summary table"),
    ("tables/BiGSCAPE_BGC_to_GCF.tsv", "Tables", "BiG-SCAPE BGC-to-GCF assignments across cutoffs"),
    ("tables/AF3_model_summary.tsv", "Tables", "AF3 QC model summary for the current integrated subset"),
    ("tables/Foldseek_besthit_all.tsv", "Tables", "Foldseek best-hit table for proteins with Foldseek annotation"),
    ("tables/Foldseek_AF3QC_merged_all.tsv", "Tables", "Foldseek and AF3 QC merged table"),
    ("tables/PHRC_integrated_BGC_protein_structure_summary.tsv", "Tables", "Integrated public protein-structure summary"),
    ("tables/column_dictionary.tsv", "Documentation", "Column dictionary"),
    ("sequences/BGC_proteins.faa", "Sequences", "BGC protein FASTA"),
    ("antismash/region_gbk.tar.gz", "antiSMASH", "antiSMASH region GenBank archive"),
    ("antismash/antismash_PRHC_samples.sqsh", "antiSMASH", "antiSMASH archive"),
    ("bigscape/gcf_tables.tar.gz", "BiG-SCAPE", "BiG-SCAPE GCF tables"),
    ("bigscape/networks.tar.gz", "BiG-SCAPE", "BiG-SCAPE network files"),
    ("bigscape/cytoscape_files.tar.gz", "BiG-SCAPE", "Cytoscape export archive"),
    ("structures/AF3_final_models_short.tar.gz", "Structures", "Short predicted structure CIF archive"),
    ("structures/AF3_final_models_medium.tar.gz", "Structures", "Medium predicted structure CIF archive"),
    ("structures/AF3_final_models_long.tar.gz", "Structures", "Long and very-long predicted structure CIF archive"),
    ("foldseek/Foldseek_besthit_all.tsv.gz", "Foldseek", "Compressed Foldseek best-hit table"),
    ("foldseek/Foldseek_AF3QC_merged_all.tsv.gz", "Foldseek", "Compressed Foldseek AF3 QC merged table"),
    ("foldseek/raw_foldseek_outputs.tar.gz", "Foldseek", "Raw Foldseek output archive"),
    ("docs/README.md", "Documentation", "Package README"),
    ("docs/data_processing_workflow.md", "Documentation", "Data processing workflow"),
    ("docs/citation.txt", "Documentation", "Citation text"),
    ("docs/column_dictionary.tsv", "Documentation", "Documentation column dictionary"),
    ("checksums/md5sums.txt", "Checksums", "MD5 checksum manifest"),
]

ACCESSION_RELEASE_FILES = [
    ("metadata/tables/PHRC_integrated_BGC_protein_structure_summary.tsv", "Tables", "Accession-based integrated BGC, protein, structure, AF3 QC, and Foldseek/PDB metadata"),
    ("metadata/tables/MAG_summary.tsv", "Tables", "Accession-based MAG summary table"),
    ("metadata/tables/BGC_summary.tsv", "Tables", "Accession-based BGC summary table"),
    ("metadata/tables/BGC_protein_summary.tsv", "Tables", "Accession-based BGC protein summary table"),
    ("metadata/tables/BiGSCAPE_GCF_summary.tsv", "Tables", "BGS primary c0.3 GCF summary table"),
    ("metadata/tables/BiGSCAPE_BGC_to_GCF.tsv", "Tables", "BGS BGC-to-GCF assignments across cutoffs"),
    ("metadata/tables/AF3_model_summary.tsv", "Tables", "AF3 QC model summary for the accession release"),
    ("metadata/tables/Foldseek_besthit_all.tsv", "Foldseek", "Foldseek best-hit table for proteins with Foldseek annotation"),
    ("metadata/tables/Foldseek_AF3QC_merged_all.tsv", "Foldseek", "Foldseek and AF3 QC merged table"),
    ("metadata/tables/column_dictionary.tsv", "Documentation", "Column dictionary"),
    ("metadata/BGS_public_accession_mapping.tsv", "Documentation", "Public BGS accession mapping"),
    ("sequences/BGS_BGC_proteins_v1.0.faa", "Sequences", "BGS accession protein FASTA"),
    ("antismash/BGS_BGC_GBK_v1.0.tar.gz", "antiSMASH", "BGS accession antiSMASH region GenBank archive"),
    ("structures/BGS_structures_short_v1.0.tar.gz", "Structures", "BGS short predicted structure CIF archive"),
    ("structures/BGS_structures_medium_v1.0.tar.gz", "Structures", "BGS medium predicted structure CIF archive"),
    ("structures/BGS_structures_long_v1.0.tar.gz", "Structures", "BGS long predicted structure CIF archive"),
    ("manifests/sha256sums.txt", "Checksums", "SHA-256 checksum manifest"),
    ("manifests/md5sums.txt", "Checksums", "MD5 checksum manifest"),
    ("manifests/public_file_manifest.tsv", "Checksums", "Public file manifest"),
]


def table_dir(root: Path) -> Path:
    accession_tables = root / "metadata" / "tables"
    return accession_tables if accession_tables.exists() else root / "tables"


def public_id(dataset, value):
    return f"{dataset}|{value}" if value else ""


def clean_columns(cols):
    cleaned = []
    for col in cols:
        lower = col.lower()
        if col in SENSITIVE_COLUMNS or col in PATH_COLUMNS:
            continue
        if "internal" in lower or "triage" in lower or "drug_discovery" in lower:
            continue
        cleaned.append(col)
    return cleaned


def create_table(conn, table, cols):
    defs = ", ".join([f'"{c}" TEXT' for c in cols])
    conn.execute(f"drop table if exists {table}")
    conn.execute(f"create table {table} ({defs})")


def insert_rows(conn, table, cols, rows):
    qs = ",".join(["?"] * len(cols))
    names = ",".join([f'"{c}"' for c in cols])
    conn.executemany(f"insert into {table} ({names}) values ({qs})", ([r.get(c, "") for c in cols] for r in rows))


def load_tsv(path):
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return reader.fieldnames or [], list(reader)


def md5_map(root):
    out = {}
    p = root / "manifests/md5sums.txt"
    if not p.exists():
        p = root / "checksums/md5sums.txt"
    if p.exists():
        for line in p.read_text(errors="ignore").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                out[parts[1].lstrip("./")] = parts[0]
    return out


def sha256_map(root):
    out = {}
    p = root / "manifests/sha256sums.txt"
    if p.exists():
        for line in p.read_text(errors="ignore").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                out[parts[1].lstrip("./")] = parts[0]
    return out


def add_alias(cols: list[str], rows: list[dict[str, str]], source: str, alias: str) -> list[str]:
    if source not in cols:
        return cols
    if alias not in cols:
        cols = [alias] + cols
    for row in rows:
        row[alias] = row.get(source, "")
    return cols


def add_public_ids(table, cols, rows, dataset):
    for source, alias in ACCESSION_ALIASES.items():
        cols = add_alias(cols, rows, source, alias)
    if any(source in cols for source in ACCESSION_ALIASES):
        for row in rows:
            row["dataset"] = dataset
            if "original_mag_id" not in row and row.get("mag_id"):
                row["original_mag_id"] = row["mag_id"]
            if "original_bgc_id" not in row and row.get("bgc_id"):
                row["original_bgc_id"] = row["bgc_id"]
            if "original_protein_id" not in row and row.get("query"):
                row["original_protein_id"] = row["query"]
        if "dataset" not in cols:
            cols = ["dataset"] + cols
        for source, alias in SECONDARY_ACCESSION_ALIASES.items():
            cols = add_alias(cols, rows, source, alias)
        for col in ["original_mag_id", "original_bgc_id", "original_protein_id", "original_structure_filename"]:
            if any(row.get(col) for row in rows) and col not in cols:
                cols.append(col)
        if table == "bgc_protein_summary":
            for col in ["structure_available", "af3_qc_available", "foldseek_annotation_available"]:
                if col not in cols:
                    cols = [col] + cols
                for row in rows:
                    row[col] = "0"
        return cols, rows
    extra = ["dataset"]
    if table == "mag_summary":
        extra += ["public_mag_id"]
    elif table == "bgc_summary":
        extra += ["public_bgc_id", "public_mag_id", "public_gcf_id"]
    elif table == "bigscape_gcf_summary":
        extra += ["public_gcf_id"]
    elif table in {"bgc_protein_summary", "af3_model_summary", "foldseek_besthit_all", "foldseek_af3qc_merged_all", "integrated_summary"}:
        extra += ["public_protein_id", "public_bgc_id", "public_mag_id", "public_gcf_id"]
        if table == "bgc_protein_summary":
            extra += ["structure_available", "af3_qc_available", "foldseek_annotation_available"]
    new_cols = [c for c in extra if c not in cols] + cols
    for row in rows:
        row["dataset"] = dataset
        if "mag_id" in row:
            row["public_mag_id"] = public_id(dataset, row.get("mag_id"))
        if "genome_id" in row:
            row["public_mag_id"] = public_id(dataset, row.get("genome_id"))
        if "bgc_id" in row:
            row["public_bgc_id"] = public_id(dataset, row.get("bgc_id"))
        if "bigscape_gcf_id_full_primary" in row:
            row["public_gcf_id"] = public_id(dataset, row.get("bigscape_gcf_id_full_primary"))
        if "query" in row:
            row["public_protein_id"] = public_id(dataset, row.get("query"))
        if table == "bgc_protein_summary":
            row["structure_available"] = "0"
            row["af3_qc_available"] = "0"
            row["foldseek_annotation_available"] = "0"
    return new_cols, rows


def build_structure_map(conn, root, dataset):
    conn.execute("drop table if exists structure_file_map")
    conn.execute("""create table structure_file_map (
        public_protein_id TEXT primary key,
        public_structure_id TEXT unique,
        filename TEXT,
        relative_path TEXT,
        cif_bucket TEXT,
        protein_length_bucket TEXT,
        public_safe INTEGER
    )""")
    protein_buckets = {
        r[0]: r[1]
        for r in conn.execute("select public_protein_id, length_bucket from bgc_protein_summary")
    }
    rows = []
    missing_from_protein_table = 0
    has_accessions = conn.execute("select 1 from pragma_table_info('bgc_protein_summary') where name='public_structure_id'").fetchone()
    if has_accessions:
        for row in conn.execute("select public_protein_id, public_structure_id, length_bucket from bgc_protein_summary where coalesce(public_structure_id,'')!=''"):
            pid, sid, protein_bucket = row
            path = root / "structures" / f"{sid}.cif"
            rel = path.relative_to(root).as_posix()
            cif_bucket = protein_bucket or "unknown"
            if not protein_bucket:
                missing_from_protein_table += 1
            rows.append((pid, sid, path.name, rel, cif_bucket, protein_bucket, 1))
    else:
        for path in (root / "structures").glob("AF3_final_models_*_cif/*.cif"):
            rel = path.relative_to(root).as_posix()
            query = path.name[:-4]
            pid = public_id(dataset, query)
            cif_bucket = "short" if "short" in rel else "medium" if "medium" in rel else "long"
            protein_bucket = protein_buckets.get(pid, "")
            if not protein_bucket:
                missing_from_protein_table += 1
            rows.append((pid, None, path.name, rel, cif_bucket, protein_bucket, 1))
    conn.executemany("insert or replace into structure_file_map values (?,?,?,?,?,?,?)", rows)
    return len(rows), missing_from_protein_table


def build_download_manifest(conn, root):
    checks = md5_map(root)
    sha_checks = sha256_map(root)
    conn.execute("drop table if exists download_manifest")
    conn.execute("""create table download_manifest (
        file_key TEXT primary key,
        filename TEXT,
        relative_path TEXT,
        description TEXT,
        category TEXT,
        size_bytes INTEGER,
        compression TEXT,
        md5 TEXT,
        sha256 TEXT,
        version TEXT,
        modified_date TEXT,
        public_safe INTEGER
    )""")
    rows = []
    allowlist = ACCESSION_RELEASE_FILES if (root / "metadata" / "BGS_public_accession_mapping.tsv").exists() else LEGACY_ALLOWLIST
    for rel, category, desc in allowlist:
        if any(excluded in rel for excluded in EXCLUDED_FILES):
            continue
        path = root / rel
        if not path.exists():
            continue
        key = hashlib.sha1(rel.encode()).hexdigest()[:16]
        compression = "tar.gz" if rel.endswith(".tar.gz") else "gzip" if rel.endswith(".gz") else Path(rel).suffix.lstrip(".") or "none"
        rows.append((
            key, path.name, rel, desc, category, path.stat().st_size, compression,
            checks.get(rel, ""), sha_checks.get(rel, ""), "BGS_v1.0" if allowlist is ACCESSION_RELEASE_FILES else "PHRC_BGCStructDB_v1",
            datetime.fromtimestamp(path.stat().st_mtime).date().isoformat(), 1,
        ))
    conn.executemany("insert into download_manifest values (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def build_bgc_gbk_map(conn, root):
    conn.execute("drop table if exists bgc_gbk_map")
    conn.execute("""create table bgc_gbk_map (
        public_bgc_id TEXT primary key,
        archive_path TEXT,
        member_name TEXT,
        filename TEXT,
        public_safe INTEGER
    )""")
    archive = root / "antismash" / "BGS_BGC_GBK_v1.0.tar.gz"
    if not archive.exists():
        return 0
    rows = [
        (row[0], "antismash/BGS_BGC_GBK_v1.0.tar.gz", f"{row[0]}.gbk", f"{row[0]}.gbk", 1)
        for row in conn.execute("select public_bgc_id from bgc_summary where coalesce(public_bgc_id,'')!='' order by public_bgc_id")
    ]
    conn.executemany("insert into bgc_gbk_map values (?,?,?,?,?)", rows)
    return len(rows)


def update_availability_flags(conn):
    conn.execute("""update bgc_protein_summary
        set structure_available = case when public_protein_id in (select public_protein_id from structure_file_map) then '1' else '0' end,
            af3_qc_available = case when public_protein_id in (select public_protein_id from af3_model_summary) then '1' else '0' end,
            foldseek_annotation_available = case when public_protein_id in (select public_protein_id from foldseek_besthit_all) then '1' else '0' end
    """)


def coverage_by_length_bucket(conn):
    sql = """
    select p.length_bucket,
           count(*) as total_proteins,
           sum(case when s.public_protein_id is not null then 1 else 0 end) as available_cif_files,
           sum(case when a.public_protein_id is not null then 1 else 0 end) as af3_qc_rows,
           sum(case when f.public_protein_id is not null then 1 else 0 end) as foldseek_rows,
           sum(case when s.public_protein_id is null then 1 else 0 end) as missing_cifs,
           sum(case when s.public_protein_id is not null and a.public_protein_id is null then 1 else 0 end) as cifs_lacking_af3_qc,
           sum(case when s.public_protein_id is not null and f.public_protein_id is null then 1 else 0 end) as cifs_lacking_foldseek
    from bgc_protein_summary p
    left join structure_file_map s using(public_protein_id)
    left join af3_model_summary a using(public_protein_id)
    left join foldseek_besthit_all f using(public_protein_id)
    group by p.length_bucket
    order by case p.length_bucket when 'short' then 1 when 'medium' then 2 when 'long' then 3 when 'very_long' then 4 else 5 end
    """
    return [dict(zip([d[0] for d in conn.execute(sql).description], row)) for row in conn.execute(sql)]


def indexes(conn):
    tables = ["mag_summary", "bgc_summary", "bgc_protein_summary", "bigscape_gcf_summary", "af3_model_summary", "foldseek_besthit_all", "download_manifest", "structure_file_map"]
    cols = ["dataset", "mag_accession", "bgc_accession", "primary_gcf_accession", "protein_accession", "structure_accession", "public_mag_id", "public_bgc_id", "public_gcf_id", "public_protein_id", "public_structure_id", "original_mag_id", "original_bgc_id", "original_protein_id", "original_structure_filename", "query", "region_basename", "product", "gene_name", "sequence_length", "length_bucket", "mean_plddt", "af3_confidence_class", "compactness_class", "target", "pdb_structural_match_category", "category", "structure_available", "af3_qc_available", "foldseek_annotation_available"]
    for table in tables:
        for col in cols:
            try:
                conn.execute(f'create index if not exists idx_{table}_{col} on {table}("{col}")')
            except sqlite3.OperationalError:
                pass
    unique_indexes = [
        ("mag_summary", "public_mag_id"),
        ("bgc_summary", "public_bgc_id"),
        ("bigscape_gcf_summary", "public_gcf_id"),
        ("bgc_protein_summary", "public_protein_id"),
        ("bgc_protein_summary", "public_structure_id"),
    ]
    table_columns = {
        table: {row[1] for row in conn.execute(f"pragma table_info('{table}')")}
        for table, _ in unique_indexes
    }
    for table, col in unique_indexes:
        if col not in table_columns.get(table, set()):
            continue
        try:
            conn.execute(f'create unique index if not exists uq_{table}_{col} on {table}("{col}") where coalesce("{col}", "") != ""')
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--dataset", default="PHRC")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    root = Path(args.package_root).resolve()
    tables = table_dir(root)
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    missing = [name for name in PUBLIC_TABLES if not (tables / name).exists()]
    if missing:
        raise SystemExit("Missing required tables: " + ", ".join(missing))

    report = {
        "tables": {},
        "excluded_sensitive_files": sorted([x for x in EXCLUDED_FILES if (root / "tables" / x).exists() or (root / x).exists()]),
        "missing_identifiers": {},
        "missing_structure_files": 0,
    }
    conn = sqlite3.connect(db)
    with conn:
        for filename, table in PUBLIC_TABLES.items():
            cols, rows = load_tsv(tables / filename)
            cols = clean_columns(cols)
            rows = [{k: v for k, v in row.items() if k in cols} for row in rows]
            cols, rows = add_public_ids(table, cols, rows, args.dataset)
            create_table(conn, table, cols)
            insert_rows(conn, table, cols, rows)
            report["tables"][table] = {"rows": len(rows), "columns": len(cols)}
        structure_rows, structure_ids_missing_from_proteins = build_structure_map(conn, root, args.dataset)
        update_availability_flags(conn)
        report["structure_file_map_rows"] = structure_rows
        report["structure_ids_missing_from_proteins"] = structure_ids_missing_from_proteins
        report["download_manifest_rows"] = build_download_manifest(conn, root)
        report["bgc_gbk_map_rows"] = build_bgc_gbk_map(conn, root)
        report["coverage_by_length_bucket"] = coverage_by_length_bucket(conn)
        conn.execute("drop table if exists database_metadata")
        conn.execute("create table database_metadata (key TEXT primary key, value TEXT)")
        conn.executemany("insert into database_metadata values (?,?)", [
            ("version", "BGS_v1.0" if tables.parts[-2:] == ("metadata", "tables") else "PHRC_BGCStructDB_v1"),
            ("dataset", args.dataset),
            ("package_root", root.as_posix()),
            ("ingested_at", datetime.now(timezone.utc).isoformat()),
        ])
        indexes(conn)
    report_path = db.with_suffix(".ingestion_report.json")
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
