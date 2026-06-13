from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_remaining_browse_pages_render_real_content():
    checks = {
        "/mags": "Browse MAGs",
        "/bgcs": "Browse BGCs",
        "/gcfs": "Primary BiG-SCAPE GCF assignments at cutoff c0.3",
        "/structures": "Browse Structures",
        "/search?q=terpene": "Unified Search",
        "/networks": "BiG-SCAPE Networks",
        "/help": "What is a MAG?",
        "/about": "PHRC_BGCStructDB",
        "/contact": "Contact",
    }
    for path, expected in checks.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert expected in response.text
        assert "This workflow is planned" not in response.text


def test_entity_detail_pages_render_cross_links():
    mag = client.get("/api/mags").json()["items"][0]["public_mag_id"]
    bgc = client.get("/api/bgcs").json()["items"][0]["public_bgc_id"]
    gcf_items = client.get("/api/gcfs").json()["items"]
    gcf = next(item["public_gcf_id"] for item in gcf_items if item["public_gcf_id"])

    for path, expected in [
        ("/mags/" + mag, "Linked BGCs"),
        ("/bgcs/" + bgc, "Gene Cluster Track"),
        ("/gcfs/" + gcf, "Member BGCs"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert expected in response.text
        assert "Primary c0.3" in response.text or "primary c0.3" in response.text


def test_completed_entity_api_endpoints_have_pagination_and_detail():
    for base, key in [
        ("/api/mags", "public_mag_id"),
        ("/api/bgcs", "public_bgc_id"),
        ("/api/gcfs", "public_gcf_id"),
        ("/api/structures", "public_protein_id"),
    ]:
        payload = client.get(base + "?page=1&page_size=5").json()
        assert payload["total"] > 0
        assert len(payload["items"]) <= 5
        assert "total_pages" in payload
        assert "canonical_url" in payload["items"][0]
        if base != "/api/structures":
            detail = client.get(base + "/" + payload["items"][0][key])
            assert detail.status_code == 200
            assert detail.json()[key] == payload["items"][0][key]


def test_search_api_groups_results_and_rejects_too_short_queries():
    too_short = client.get("/api/search?q=a")
    assert too_short.status_code == 400

    response = client.get("/api/search?q=terpene&page_size=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["q"] == "terpene"
    for group in ["mags", "bgcs", "gcfs", "proteins"]:
        assert group in payload["groups"]
        assert "items" in payload["groups"][group]
        assert "total" in payload["groups"][group]


def test_public_pages_and_apis_do_not_leak_paths_or_sensitive_fields():
    paths = [
        "/mags",
        "/bgcs",
        "/gcfs",
        "/structures",
        "/search?q=terpene",
        "/api/mags",
        "/api/bgcs",
        "/api/gcfs",
        "/api/structures",
        "/api/search?q=terpene",
    ]
    forbidden = [
        f"/{'scratch'}/",
        f"/{'users'}/",
        "drug_discovery_priority_score",
        "database_candidate_tier",
        "priority_class",
    ]
    for path in paths:
        text = client.get(path).text.lower()
        for token in forbidden:
            assert token not in text, (path, token)


def test_version_api_exposes_release_metadata():
    payload = client.get("/api/version").json()
    assert payload["database_version"] == "PHRC_BGCStructDB_v1"
    assert payload["schema_version"]
    assert "PHRC" in payload["loaded_datasets"]
