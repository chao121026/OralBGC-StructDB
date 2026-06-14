import csv
import json
import subprocess
import sys
from pathlib import Path


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def make_package(root: Path) -> None:
    write_tsv(
        root / "tables" / "MAG_summary.tsv",
        [
            {"mag_id": "MAG_B"},
            {"mag_id": "MAG_A"},
        ],
    )
    write_tsv(
        root / "tables" / "BGC_summary.tsv",
        [
            {
                "region_basename": "contig_2.region001.gbk",
                "bgc_id": "BGC_B",
                "genome_id": "MAG_B",
                "contig_id": "contig_2",
                "region_number": "1",
                "bigscape_gcf_id_full_primary": "c0.3|NRPS|FAM_00002",
            },
            {
                "region_basename": "contig_1.region001.gbk",
                "bgc_id": "BGC_A",
                "genome_id": "MAG_A",
                "contig_id": "contig_1",
                "region_number": "1",
                "bigscape_gcf_id_full_primary": "c0.3|RiPP|FAM_00001",
            },
        ],
    )
    write_tsv(
        root / "tables" / "BGC_protein_summary.tsv",
        [
            {
                "query": "PRT_B",
                "bgc_id": "BGC_B",
                "genome_id": "MAG_B",
                "contig_id": "contig_2",
                "region_number": "1",
                "region_basename": "contig_2.region001.gbk",
            },
            {
                "query": "PRT_A",
                "bgc_id": "BGC_A",
                "genome_id": "MAG_A",
                "contig_id": "contig_1",
                "region_number": "1",
                "region_basename": "contig_1.region001.gbk",
            },
        ],
    )
    write_tsv(
        root / "tables" / "BiGSCAPE_GCF_summary.tsv",
        [
            {"bigscape_gcf_id_full_primary": "c0.3|RiPP|FAM_00001"},
            {"bigscape_gcf_id_full_primary": "c0.3|NRPS|FAM_00002"},
        ],
    )
    (root / "antismash" / "region_gbk").mkdir(parents=True)
    (root / "antismash" / "region_gbk" / "contig_1.region001.gbk").write_text("LOCUS A\n")
    (root / "antismash" / "region_gbk" / "contig_2.region001.gbk").write_text("LOCUS B\n")
    (root / "structures" / "AF3_final_models_short_cif").mkdir(parents=True)
    (root / "structures" / "AF3_final_models_short_cif" / "PRT_A.cif").write_text("data_PRT_A\n")


def run_migration(source_root: Path, output_root: Path, registry: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "scripts/migrate_public_accessions.py",
            "--source-root",
            str(source_root),
            "--output-root",
            str(output_root),
            "--registry",
            str(registry),
            "--release-version",
            "v1.0",
            *extra,
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def test_dry_run_assigns_deterministic_accessions_and_writes_reports(tmp_path: Path) -> None:
    source = tmp_path / "package"
    make_package(source)

    result = run_migration(source, tmp_path / "public", tmp_path / "accession_registry.tsv", "--dry-run")

    assert result.returncode == 0, result.stderr
    artifact_root = tmp_path / "public" / "artifacts" / "accession_migration"
    registry_rows = read_tsv(artifact_root / "accession_registry_preview.tsv")
    by_original = {(row["entity_type"], row["original_identifier"]): row for row in registry_rows}
    assert by_original[("MAG", "MAG_A")]["public_accession"] == "BGS-MAG-000001"
    assert by_original[("MAG", "MAG_B")]["public_accession"] == "BGS-MAG-000002"
    assert by_original[("BGC", "BGC_A")]["parent_public_accession"] == "BGS-MAG-000001"
    assert by_original[("GCF", "c0.3|NRPS|FAM_00002")]["public_accession"] == "BGS-GCF-C03-0001"
    assert by_original[("GCF", "c0.3|RiPP|FAM_00001")]["public_accession"] == "BGS-GCF-C03-0002"
    assert by_original[("STRUCTURE", "PRT_A")]["parent_public_accession"] == "BGS-PRT-000001"
    assert not (tmp_path / "public" / "antismash" / "BGS-BGC-000001.gbk").exists()
    assert (artifact_root / "file_rename_plan.tsv").exists()
    assert json.loads((artifact_root / "count_summary.json").read_text())["records_mapped"]["BGC"] == 2


def test_dry_run_reuses_existing_registry_and_allocates_new_suffixes(tmp_path: Path) -> None:
    source = tmp_path / "package"
    make_package(source)
    registry = tmp_path / "accession_registry.tsv"
    registry.write_text(
        "\t".join(
            [
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
        )
        + "\n"
        + "\t".join(["MAG", "BGS-MAG-000099", "PHRC", "MAG_A", "", "", "", "", "", "", "", "v0.9", "active", "", "", "", ""])
        + "\n"
    )

    result = run_migration(source, tmp_path / "public", registry, "--dry-run")

    assert result.returncode == 0, result.stderr
    rows = read_tsv(tmp_path / "public" / "artifacts" / "accession_migration" / "accession_registry_preview.tsv")
    by_original = {(row["entity_type"], row["original_identifier"]): row for row in rows}
    assert by_original[("MAG", "MAG_A")]["public_accession"] == "BGS-MAG-000099"
    assert by_original[("MAG", "MAG_B")]["public_accession"] == "BGS-MAG-000100"


def test_apply_is_rejected_when_required_parent_reference_is_missing(tmp_path: Path) -> None:
    source = tmp_path / "package"
    make_package(source)
    rows = read_tsv(source / "tables" / "BGC_summary.tsv")
    rows[0]["genome_id"] = "MISSING_MAG"
    write_tsv(source / "tables" / "BGC_summary.tsv", rows)

    result = run_migration(source, tmp_path / "public", tmp_path / "registry.tsv", "--apply")

    assert result.returncode != 0
    assert "missing parent relationships" in result.stderr
    missing_rows = read_tsv(tmp_path / "public" / "artifacts" / "accession_migration" / "missing_reference_report.tsv")
    assert missing_rows[0]["missing_parent_identifier"] == "MISSING_MAG"


def test_validator_accepts_dry_run_registry_preview(tmp_path: Path) -> None:
    source = tmp_path / "package"
    output = tmp_path / "public"
    make_package(source)
    dry_run = run_migration(source, output, tmp_path / "registry.tsv", "--dry-run")
    assert dry_run.returncode == 0, dry_run.stderr

    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_accession_migration.py",
            "--registry",
            str(output / "artifacts" / "accession_migration" / "accession_registry_preview.tsv"),
            "--release-root",
            str(output),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert '"errors": 0' in result.stdout
