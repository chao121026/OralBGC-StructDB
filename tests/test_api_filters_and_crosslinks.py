from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_mag_api_search_and_detail_crosslinks():
    first = client.get("/api/mags?page=1&page_size=1").json()["items"][0]
    mag_id = first["public_mag_id"]
    found = client.get("/api/mags", params={"q": first["mag_id"], "page_size": 5}).json()
    assert any(item["public_mag_id"] == mag_id for item in found["items"])
    detail = client.get("/mags/" + mag_id)
    assert detail.status_code == 200
    assert "/bgcs?mag=" + mag_id in detail.text


def test_bgc_api_filters_assigned_and_unassigned_primary_gcf():
    assigned = client.get("/api/bgcs", params={"assigned": "assigned", "page_size": 10}).json()
    unassigned = client.get("/api/bgcs", params={"assigned": "unassigned", "page_size": 10}).json()
    assert assigned["total"] > 0
    assert unassigned["total"] > 0
    assert all(item["public_gcf_id"] for item in assigned["items"])
    assert all(not item["public_gcf_id"] for item in unassigned["items"])


def test_gcf_api_class_filter_and_detail_labeling():
    gcfs = client.get("/api/gcfs", params={"bgc_class": "terpene", "page_size": 5}).json()
    assert gcfs["total"] > 0
    assert all(item["bigscape_class_primary"] == "terpene" for item in gcfs["items"])
    detail = client.get("/gcfs/" + gcfs["items"][0]["public_gcf_id"])
    assert detail.status_code == 200
    assert "BGS-GCF-C03-" in detail.text


def test_structure_browse_includes_cif_only_records():
    structures = client.get("/api/structures", params={"af3_qc_available": "0", "foldseek_annotation_available": "0", "page_size": 10}).json()
    assert structures["total"] > 0
    assert all(item["structure_available"] == "1" for item in structures["items"])
    assert all(item["af3_qc_available"] == "0" for item in structures["items"])


def test_invalid_sort_falls_back_to_safe_default():
    payload = client.get("/api/bgcs", params={"sort_by": "region_file", "page_size": 3}).json()
    assert payload["sort_by"] == "public_bgc_id"
    assert len(payload["items"]) == 3


def test_max_page_size_is_enforced():
    payload = client.get("/api/structures", params={"page_size": 10000}).json()
    assert payload["page_size"] == 100
    assert len(payload["items"]) <= 100


def test_networks_page_lists_real_archives_only():
    response = client.get("/networks")
    assert response.status_code == 200
    assert "BiG-SCAPE gene cluster families" in response.text
    assert "179" in response.text
    assert "1,744" in response.text or "1,913" in response.text
    assert "BGS-GCF-C03-" in response.text
    assert "network archive" in response.text.lower()
    assert "Direct Cytoscape.js rendering is deferred" not in response.text
    assert "No example networks are fabricated" not in response.text
    assert "Future bounded viewer controls" not in response.text


def test_bigscape_summary_api_uses_public_counts_and_no_paths():
    response = client.get("/api/bigscape/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["primary_cutoff"] == "0.3"
    assert payload["primary_gcf_count"] == 179
    assert payload["assigned_bgc_count"] > 0
    assert payload["bgc_count"] == 1913
    assert payload["class_count"] > 0
    assert "/Users/" not in response.text
    assert "raw_import" not in response.text


def test_bigscape_download_manifest_excludes_raw_and_empty_cytoscape():
    payload = client.get("/api/downloads").json()
    names = {item["filename"] for item in payload["items"]}
    text = str(payload)
    assert "bigscape_public_tables.tar.gz" in names
    assert "bigscape_primary_c0.3_networks.tar.gz" in names
    assert "cytoscape_files.tar.gz" not in names
    assert "raw_import_2026-06-12" not in text
    assert "/Users/" not in text


def test_help_about_contact_are_public_no_login_pages():
    for path in ["/help", "/about", "/contact"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "login" not in response.text.lower() or "no login" in response.text.lower()


def test_download_manifest_remains_allowlist_based():
    payload = client.get("/api/downloads").json()
    names = {item["filename"] for item in payload["items"]}
    assert "PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv" not in names
    assert "candidate_peptides.faa" not in names
    assert "BGS_BGC_GBK_v1.0.tar.gz" in names
    assert "region_gbk.tar.gz" not in names
