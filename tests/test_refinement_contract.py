import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

DB = Path("app/data/phrc_bgcstructdb.sqlite")


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def test_homepage_stats_distinguish_structure_qc_and_foldseek():
    client = TestClient(app)
    payload = client.get("/api/stats").json()
    assert payload["predicted_structures_available"] == 22622
    assert payload["proteins_with_af3_qc"] == 10972
    assert payload["proteins_with_foldseek_annotation"] == 10972
    assert "af3_models" not in payload


def test_generated_sqlite_has_no_raw_local_paths_or_path_columns():
    conn = db()
    forbidden_columns = {"model_cif", "region_file", "bigscape_source_file", "region_file_ranking"}
    public_tables = [
        "mag_summary", "bgc_summary", "bgc_protein_summary", "bigscape_gcf_summary",
        "bigscape_bgc_to_gcf", "af3_model_summary", "foldseek_besthit_all",
        "foldseek_af3qc_merged_all", "integrated_summary", "column_dictionary",
    ]
    for table in public_tables:
        cols = [r[1] for r in conn.execute(f"pragma table_info({table})")]
        assert not (forbidden_columns & set(cols)), f"{table} has raw path columns"
        for col in cols:
            count = conn.execute(
                f"""select count(*) from {table}
                    where "{col}" like '/' || 'Users' || '/%' or "{col}" like '/' || 'scratch' || '/%' """
            ).fetchone()[0]
            assert count == 0, f"{table}.{col} contains local filesystem paths"


def test_public_apis_expose_no_sensitive_candidate_fields_or_raw_paths():
    client = TestClient(app)
    for path in ["/api/proteins?page=1&page_size=25", "/api/downloads"]:
        text = client.get(path).text.lower()
        assert f"/{'scratch'}/" not in text
        assert f"/{'users'}/" not in text
        assert "drug_discovery_priority_score" not in text
        assert "priority_class" not in text
        assert "database_candidate_tier" not in text


def test_detail_states_for_short_cif_only_and_no_cif_records():
    conn = db()
    short = conn.execute("""select public_protein_id from bgc_protein_summary
        where structure_available='1' and af3_qc_available='1' and foldseek_annotation_available='1'
        order by public_protein_id limit 1""").fetchone()[0]
    cif_only = conn.execute("""select public_protein_id from bgc_protein_summary
        where structure_available='1' and af3_qc_available='0' and foldseek_annotation_available='0'
        order by public_protein_id limit 1""").fetchone()[0]
    no_cif = conn.execute("""select public_protein_id from bgc_protein_summary
        where structure_available='0' order by public_protein_id limit 1""").fetchone()[0]

    client = TestClient(app)
    short_html = client.get("/proteins/" + short).text
    assert "AF3 QC available" in short_html
    assert "Foldseek/PDB annotation available" in short_html

    cif_only_html = client.get("/proteins/" + cif_only).text
    assert "Predicted structure available; AF3 QC and Foldseek annotations are not yet available in this release." in cif_only_html
    assert "<dd>0</dd>" not in cif_only_html

    no_cif_html = client.get("/proteins/" + no_cif).text
    assert "Predicted structure is not available for this protein in the current public package." in no_cif_html
    assert "Download CIF" not in no_cif_html


def test_gcf_stats_document_primary_c03_cutoff():
    client = TestClient(app)
    payload = client.get("/api/stats").json()
    assert payload["primary_c03_gcfs"] == 179
    assert payload["bgcs_with_primary_gcf"] == 1744
    assert payload["bgcs_without_primary_gcf"] == 169
