from urllib.parse import quote

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_database_uses_bgs_accessions_and_preserves_counts():
    stats = client.get("/api/stats").json()

    assert stats["mags"] == 583
    assert stats["bgcs"] == 1913
    assert stats["primary_c03_gcfs"] == 179
    assert stats["bgc_proteins"] == 22626
    assert stats["predicted_structures_available"] == 22622
    assert stats["proteins_with_af3_qc"] == 10972
    assert stats["proteins_with_foldseek_annotation"] == 10972

    mag = client.get("/api/mags", params={"page_size": 1}).json()["items"][0]
    bgc = client.get("/api/bgcs", params={"page_size": 1}).json()["items"][0]
    gcf = client.get("/api/gcfs", params={"page_size": 1}).json()["items"][0]
    protein = client.get("/api/proteins", params={"page_size": 1}).json()["items"][0]

    assert mag["mag_accession"].startswith("BGS-MAG-")
    assert mag["original_mag_id"]
    assert bgc["bgc_accession"].startswith("BGS-BGC-")
    assert bgc["original_bgc_id"]
    assert gcf["gcf_accession"].startswith("BGS-GCF-C03-")
    assert protein["protein_accession"].startswith("BGS-PRT-")
    assert protein["original_protein_id"]


def test_canonical_accession_urls_and_legacy_redirects():
    protein = client.get("/api/proteins", params={"page_size": 1}).json()["items"][0]
    bgc = client.get("/api/bgcs", params={"page_size": 1}).json()["items"][0]

    assert client.get(f"/proteins/{protein['protein_accession']}").status_code == 200
    assert client.get(f"/bgcs/{bgc['bgc_accession']}").status_code == 200

    legacy = protein["original_protein_id"]
    response = client.get(f"/proteins/{quote(legacy, safe='')}", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"].endswith(f"/proteins/{protein['protein_accession']}")

    literal = client.get(f"/proteins/{legacy}", follow_redirects=False)
    assert literal.status_code == 308
    assert literal.headers["location"].endswith(f"/proteins/{protein['protein_accession']}")


def test_search_accepts_accession_original_identifier_and_filename():
    bgc = client.get("/api/bgcs", params={"page_size": 1}).json()["items"][0]

    for query in [bgc["bgc_accession"], bgc["original_bgc_id"], bgc["region_basename"]]:
        payload = client.get("/api/search", params={"q": query, "page_size": 5}).json()
        items = payload["groups"]["bgcs"]["items"]
        assert any(item["bgc_accession"] == bgc["bgc_accession"] for item in items)
        assert all(item["canonical_url"].startswith("/bgcs/BGS-BGC-") for item in items)


def test_structure_accession_serves_cif_without_using_legacy_filename():
    structure = client.get("/api/structures", params={"page_size": 1}).json()["items"][0]

    assert structure["structure_accession"].startswith("BGS-STR-")
    response = client.get(f"/structures/cif/{structure['structure_accession']}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("chemical/x-cif")
    assert f'{structure["structure_accession"]}.cif' in response.headers["content-disposition"]


def test_downloads_are_accession_release_primary_files():
    payload = client.get("/api/downloads").json()
    names = {item["filename"]: item for item in payload["items"]}

    for filename in [
        "BGS_public_accession_mapping.tsv",
        "BGS_BGC_proteins_v1.0.faa",
        "BGS_BGC_GBK_v1.0.tar.gz",
        "BGS_structures_short_v1.0.tar.gz",
        "BGS_structures_medium_v1.0.tar.gz",
        "BGS_structures_long_v1.0.tar.gz",
        "sha256sums.txt",
    ]:
        assert filename in names

    recommended_names = {item["filename"] for item in payload["items"] if item["audience_level"] == "recommended"}
    assert "BGS_public_accession_mapping.tsv" in recommended_names
    assert "region_gbk.tar.gz" not in recommended_names
    assert all("/Users/" not in str(item) and "/scratch/" not in str(item) for item in payload["items"])


def test_individual_bgc_gbk_download_uses_accession_member():
    bgc = client.get("/api/bgcs", params={"page_size": 1}).json()["items"][0]

    response = client.get(f"/bgcs/gbk/{bgc['bgc_accession']}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("chemical/x-genbank")
    assert f'{bgc["bgc_accession"]}.gbk' in response.headers["content-disposition"]
    assert b"LOCUS" in response.content[:200]
