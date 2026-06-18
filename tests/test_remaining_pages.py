from fastapi.testclient import TestClient
from bs4 import BeautifulSoup

from app.main import app


client = TestClient(app)


def test_remaining_browse_pages_render_real_content():
    checks = {
        "/mags": "Browse MAGs",
        "/bgcs": "Browse BGCs",
        "/gcfs": "Primary BiG-SCAPE GCF assignments at cutoff c0.3",
        "/structures": "Browse Structures",
        "/search?q=terpene": "Search OralBGC-StructDB",
        "/networks": "BiG-SCAPE gene cluster families",
        "/help": "What is a MAG?",
        "/about": "OralBGC-StructDB",
        "/contact": "Contact",
    }
    for path, expected in checks.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert expected in response.text
        assert "This workflow is planned" not in response.text


def test_search_page_preserves_working_search_without_sequence_placeholder():
    response = client.get("/search")
    soup = BeautifulSoup(response.text, "html.parser")
    examples = [
        "BGS-MAG-000283",
        "BGS-BGC-000001",
        "BGS-GCF-C03-0003",
        "BGS-PRT-000001",
        "BGS-STR-000001",
        "NRPS",
        "terpene",
    ]

    assert response.status_code == 200
    assert "Search OralBGC-StructDB" in response.text
    form = soup.find("form", method="get", action="/search")
    assert form is not None
    assert form.find("input", attrs={"name": "q"}) is not None

    example_block = soup.select_one(".search-examples")
    assert example_block is not None
    for example in examples:
        assert example in response.text
        example_node = example_block.find(string=example)
        assert example_node is not None
        assert example_node.find_parent("a") is None
        assert example_node.find_parent(attrs={"href": True}) is None
        assert example_node.find_parent(attrs={"role": "button"}) is None
        assert example_node.find_parent(attrs={"tabindex": "0"}) is None

    for removed in [
        "Sequence Search",
        "MMseqs2",
        "BLASTp",
        "planned for a future release",
        "future asynchronous",
        "sequence-search",
        ">protein_sequence",
        "<textarea",
    ]:
        assert removed not in response.text


def test_search_page_still_returns_indexed_results_and_no_sequence_routes():
    response = client.get("/search?q=BGS-MAG-000283")
    soup = BeautifulSoup(response.text, "html.parser")

    assert response.status_code == 200
    assert "BGS-MAG-000283" in response.text
    assert soup.find("a", href="/mags/BGS-MAG-000283") is not None
    assert client.get("/search/sequence").status_code == 404
    assert client.get("/api/sequence-search").status_code == 404


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
        assert "BGS-" in response.text


def test_completed_entity_api_endpoints_have_pagination_and_detail():
    for base, key in [
        ("/api/mags", "public_mag_id"),
        ("/api/bgcs", "public_bgc_id"),
        ("/api/gcfs", "public_gcf_id"),
        ("/api/structures", "public_structure_id"),
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


def test_protein_browse_table_keeps_foldseek_score_match_and_action_columns_separate():
    response = client.get("/proteins")
    soup = BeautifulSoup(response.text, "html.parser")

    assert response.status_code == 200
    wrapper = soup.select_one(".protein-table-wrapper")
    assert wrapper is not None
    table = wrapper.select_one("table.protein-table")
    assert table is not None

    row = next(
        tr for tr in table.select("tbody tr")
        if "Foldseek/PDB annotation available" in tr.get_text(" ", strip=True)
        and "Weak Or No Clear PDB Match" in tr.get_text(" ", strip=True)
    )
    assert row.select_one(".annotation-column").get_text(" ", strip=True) == "Foldseek/PDB annotation available"
    assert row.select_one(".score-column").get_text(" ", strip=True) == "59.1"
    assert row.select_one(".match-column").get_text(" ", strip=True) == "Weak Or No Clear PDB Match"
    assert row.select_one(".action-column").get_text(" ", strip=True) == "Open"
    assert row.select_one(".action-column a.detail-link")["href"].startswith("/proteins/")

    css = open("app/static/css/site.css").read()
    assert ".protein-table-wrapper" in css
    assert ".protein-table" in css
    assert "position: absolute" not in css[css.find(".protein-table-wrapper"):]


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
    assert payload["database_version"] == "BGS_v1.0"
    assert payload["schema_version"]
    assert "PHRC" in payload["loaded_datasets"]
