import csv
import io
import json
import subprocess
import sys
import tarfile
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


def write_gbk_archive(root: Path, members: dict[str, bytes]) -> None:
    archive = root / "antismash" / "region_gbk.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(content))


def simple_genbank(record_id: str, sequence: str = "ATGCATGCATGC", *, include_region: bool = True) -> bytes:
    features = ""
    if include_region:
        features = """     region          1..12
                     /region_number=\"1\"
                     /product=\"RiPP-like\"
     protocluster    1..12
                     /product=\"RiPP-like\"
"""
    return f"""LOCUS       {record_id[:16]:<16} {len(sequence):>7} bp    DNA     linear   BCT 01-JAN-2000
DEFINITION  {record_id}.
ACCESSION   {record_id}
VERSION     {record_id}
KEYWORDS    .
SOURCE      synthetic construct
  ORGANISM  synthetic construct
            .
FEATURES             Location/Qualifiers
     source          1..{len(sequence)}
                     /organism=\"synthetic construct\"
{features}ORIGIN
        1 {sequence.lower()}
//
""".encode()


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
            "--phase",
            "dry-run",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert '"errors": 0' in result.stdout


def test_dry_run_registry_generation_is_byte_identical(tmp_path: Path) -> None:
    source = tmp_path / "package"
    make_package(source)
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_result = run_migration(source, first, tmp_path / "registry.tsv", "--dry-run")
    second_result = run_migration(source, second, tmp_path / "registry.tsv", "--dry-run")

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    first_registry = first / "artifacts" / "accession_migration" / "accession_registry_preview.tsv"
    second_registry = second / "artifacts" / "accession_migration" / "accession_registry_preview.tsv"
    assert first_registry.read_bytes() == second_registry.read_bytes()


def test_gbk_archive_inventory_matches_members_and_reports_missing_bgcs(tmp_path: Path) -> None:
    source = tmp_path / "package"
    make_package(source)
    write_gbk_archive(
        source,
        {
            "contig_1.region001.gbk": b"LOCUS contig_1\n",
            "extra.region001.gbk": b"LOCUS extra\n",
        },
    )

    result = run_migration(source, tmp_path / "public", tmp_path / "registry.tsv", "--dry-run")

    assert result.returncode == 0, result.stderr
    artifact_root = tmp_path / "public" / "artifacts" / "accession_migration"
    inventory = read_tsv(artifact_root / "gbk_archive_inventory.tsv")
    by_basename = {row["basename"]: row for row in inventory if row["basename"]}
    assert by_basename["contig_1.region001.gbk"]["match_status"] == "matched"
    assert by_basename["contig_1.region001.gbk"]["matched_bgc_accession"] == "BGS-BGC-000001"
    assert by_basename["extra.region001.gbk"]["match_status"] == "unmatched"
    missing = [row for row in inventory if row["match_status"] == "bgc_without_gbk"]
    assert missing[0]["matched_bgc_accession"] == "BGS-BGC-000002"
    transform = read_tsv(artifact_root / "gbk_transform_plan.tsv")
    assert transform[0]["target_member"] == "BGS-BGC-000001.gbk"
    assert transform[0]["content_change_required"] == "structured_comment_only"


def test_gbk_archive_inventory_reports_unsafe_and_duplicate_members(tmp_path: Path) -> None:
    source = tmp_path / "package"
    make_package(source)
    archive = source / "antismash" / "region_gbk.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        for name in ["../escape.gbk", "/absolute.gbk", "nested/contig_1.region001.gbk", "contig_1.region001.gbk", "contig_1.region001.gbk", "notes.txt"]:
            content = b"LOCUS unsafe\n"
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(content))

    result = run_migration(source, tmp_path / "public", tmp_path / "registry.tsv", "--dry-run")

    assert result.returncode == 0, result.stderr
    rows = read_tsv(tmp_path / "public" / "artifacts" / "accession_migration" / "gbk_archive_inventory.tsv")
    statuses = {row["archive_member"]: row["match_status"] for row in rows}
    assert statuses["../escape.gbk"] == "unsafe_path"
    assert statuses["/absolute.gbk"] == "unsafe_path"
    assert statuses["nested/contig_1.region001.gbk"] == "unexpected_directory"
    assert statuses["notes.txt"] == "non_gbk"
    assert [row["match_status"] for row in rows if row["archive_member"] == "contig_1.region001.gbk"] == [
        "duplicate_basename",
        "duplicate_basename",
    ]


def test_public_mapping_excludes_absolute_paths(tmp_path: Path) -> None:
    source = tmp_path / "package"
    make_package(source)

    result = run_migration(source, tmp_path / "public", tmp_path / "registry.tsv", "--dry-run")

    assert result.returncode == 0, result.stderr
    mapping = (tmp_path / "public" / "artifacts" / "accession_migration" / "public_accession_mapping.tsv").read_text()
    assert str(tmp_path) not in mapping
    assert "source_path" not in mapping.splitlines()[0]
    assert "public_path" not in mapping.splitlines()[0]


def test_validator_phase_controls_missing_public_file_severity(tmp_path: Path) -> None:
    source = tmp_path / "package"
    output = tmp_path / "public"
    make_package(source)
    dry_run = run_migration(source, output, tmp_path / "registry.tsv", "--dry-run")
    assert dry_run.returncode == 0, dry_run.stderr
    registry = output / "artifacts" / "accession_migration" / "accession_registry_preview.tsv"

    dry_result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_accession_migration.py",
            "--registry",
            str(registry),
            "--release-root",
            str(output),
            "--phase",
            "dry-run",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    applied_result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_accession_migration.py",
            "--registry",
            str(registry),
            "--release-root",
            str(output),
            "--phase",
            "applied",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    dry_report = json.loads(dry_result.stdout)
    applied_report = json.loads(applied_result.stdout)
    assert dry_result.returncode == 0, dry_result.stderr
    assert dry_report["warnings"] == 0
    assert dry_report["planned_files"] == 3
    assert applied_result.returncode == 1
    assert applied_report["errors"] == 3


def test_planned_genbank_structured_comment_payload_is_biopython_compatible() -> None:
    from scripts.migrate_public_accessions import planned_bgc_structured_comment

    payload = planned_bgc_structured_comment(
        public_accession="BGS-BGC-000001",
        source_collection="PHRC",
        original_identifier="legacy_bgc",
        original_filename="legacy.region001.gbk",
    )

    assert payload == {
        "PHRC_BGCStructDB": {
            "Public-Accession": "BGS-BGC-000001",
            "Source-Collection": "PHRC",
            "Original-BGC-Identifier": "legacy_bgc",
            "Original-Filename": "legacy.region001.gbk",
        }
    }


def test_unmatched_gbk_review_classifies_extra_region_and_apply_requires_manifest(tmp_path: Path) -> None:
    source = tmp_path / "package"
    output = tmp_path / "public"
    make_package(source)
    write_gbk_archive(
        source,
            {
                "contig_1.region001.gbk": simple_genbank("contig_1"),
                "contig_2.region001.gbk": simple_genbank("contig_2"),
            "MAG_A/extra.region001.gbk": simple_genbank("extra", "AAAACCCCGGGG"),
            },
        )

    dry_run = run_migration(source, output, tmp_path / "registry.tsv", "--dry-run")
    assert dry_run.returncode == 0, dry_run.stderr
    review = read_tsv(output / "artifacts" / "accession_migration" / "unmatched_gbk_review.tsv")
    assert review[0]["classification"] == "superseded_record"
    assert review[0]["recommended_action"] == "exclude_from_public_archive"
    exclusion = read_tsv(output / "artifacts" / "accession_migration" / "gbk_exclusion_manifest.tsv")
    assert exclusion[0]["review_status"] == "approved_for_exclusion"

    apply_without_manifest = run_migration(source, tmp_path / "apply1", tmp_path / "registry.tsv", "--apply")
    assert apply_without_manifest.returncode == 2
    assert "unapproved extra GBK archive members" in apply_without_manifest.stderr

    apply_with_manifest = run_migration(
        source,
        tmp_path / "apply2",
        tmp_path / "registry.tsv",
        "--gbk-exclusion-manifest",
        str(output / "artifacts" / "accession_migration" / "gbk_exclusion_manifest.tsv"),
        "--apply",
    )
    assert apply_with_manifest.returncode == 0, apply_with_manifest.stderr


def test_unmatched_gbk_review_detects_auxiliary_non_region_file(tmp_path: Path) -> None:
    source = tmp_path / "package"
    output = tmp_path / "public"
    make_package(source)
    write_gbk_archive(
        source,
        {
            "contig_1.region001.gbk": simple_genbank("contig_1"),
            "contig_2.region001.gbk": simple_genbank("contig_2"),
            "MAG_A/auxiliary.gbk": simple_genbank("auxiliary", include_region=False),
        },
    )

    result = run_migration(source, output, tmp_path / "registry.tsv", "--dry-run")

    assert result.returncode == 0, result.stderr
    review = read_tsv(output / "artifacts" / "accession_migration" / "unmatched_gbk_review.tsv")
    assert review[0]["classification"] == "auxiliary_non_region_file"


def test_unmatched_gbk_review_detects_duplicate_sequence(tmp_path: Path) -> None:
    source = tmp_path / "package"
    output = tmp_path / "public"
    make_package(source)
    write_gbk_archive(
        source,
        {
            "contig_1.region001.gbk": simple_genbank("contig_1", "ATGCATGCATGC"),
            "contig_2.region001.gbk": simple_genbank("contig_2", "TTTTCCCCAAAA"),
            "MAG_A/extra.region001.gbk": simple_genbank("extra", "ATGCATGCATGC"),
        },
    )

    result = run_migration(source, output, tmp_path / "registry.tsv", "--dry-run")

    assert result.returncode == 0, result.stderr
    review = read_tsv(output / "artifacts" / "accession_migration" / "unmatched_gbk_review.tsv")
    assert review[0]["classification"] == "duplicate_content"
    assert review[0]["candidate_existing_bgc_accession"] == "BGS-BGC-000001"
