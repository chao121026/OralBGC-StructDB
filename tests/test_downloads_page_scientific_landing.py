import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


client = TestClient(app)


def downloads_page(monkeypatch):
    monkeypatch.setenv("GLOBUS_RELEASE_RELATIVE_ROOT", "staging/v1")
    get_settings.cache_clear()
    response = client.get("/downloads")
    get_settings.cache_clear()
    assert response.status_code == 200
    return response


def download_hrefs(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [a.get("href", "") for a in soup.find_all("a") if a.get("href")]


def section_links(html: str, section_key: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    section = soup.find(attrs={"data-download-section": section_key})
    assert section is not None
    return {a.get_text(strip=True): a.get("href", "") for a in section.find_all("a")}


def test_downloads_page_is_scientific_landing_page(monkeypatch):
    response = downloads_page(monkeypatch)
    text = response.text

    for heading in [
        "MAG assemblies",
        "BGC sequences",
        "GCF and BiG-SCAPE results",
        "Protein sequences",
        "3D protein structures",
    ]:
        assert heading in text

    for label in [
        "Download MAG FASTA",
        "Browse BGCs",
        "Download BGC archive",
        "Download GCF/BiG-SCAPE results",
        "Download complete protein FASTA",
        "Download structure archive",
        "Browse individual structures",
    ]:
        assert label in text

    assert "Recommended data" not in text
    assert "Advanced analysis and reproducibility files" not in text


def test_bgc_download_card_links_to_bgc_browse_route(monkeypatch):
    response = downloads_page(monkeypatch)
    soup = BeautifulSoup(response.text, "html.parser")
    bgc_card = soup.find(attrs={"data-download-section": "bgc"})
    assert bgc_card is not None
    bgc_links = {a.get_text(strip=True): a.get("href", "") for a in bgc_card.find_all("a")}

    assert bgc_links["Browse BGCs"] == str(app.url_path_for("bgcs_page"))
    assert "BGS_BGC_GBK_v1.0.tar.gz" in bgc_links["Download BGC archive"]
    assert "Browse BGCs" in bgc_card.get_text(" ", strip=True)
    assert "Download BGC archive" in bgc_card.get_text(" ", strip=True)
    assert "Browse in Globus" not in response.text
    assert "app.globus.org" not in response.text


def test_downloads_page_hides_tsv_and_administrative_resources(monkeypatch):
    response = downloads_page(monkeypatch)
    text = response.text
    hrefs = download_hrefs(text)

    assert not [href for href in hrefs if re.search(r"\.tsv(\.gz)?(?:$|[?#])", href)]
    for forbidden in [
        "public_metadata",
        "release_metadata",
        "manifest.tsv",
        "network_file_manifest.tsv",
        "sha256sums",
        "md5sums",
        "checksum",
        "BGS_public_accession_mapping.tsv",
        "PHRC_integrated_BGC_protein_structure_summary.tsv",
        "exclusion",
        "migration",
        "inventory",
        "validation_summary",
        "mapping_validation",
        "Browse in Globus",
        "Open in Globus",
        "Transfer with Globus",
        "View collection",
        "app.globus.org",
    ]:
        assert forbidden.lower() not in text.lower()


def test_downloads_page_uses_direct_https_and_does_not_fabricate_gcf_archive(monkeypatch):
    response = downloads_page(monkeypatch)
    hrefs = download_hrefs(response.text)
    direct_downloads = [href for href in hrefs if "g-f2d91c.6d8b.03c0.data.globus.org" in href]

    assert direct_downloads
    assert all(href.startswith("https://g-f2d91c.6d8b.03c0.data.globus.org/staging/v1/") for href in direct_downloads)
    assert all("app.globus.org" not in href for href in hrefs)
    assert not any("gcf" in href.lower() and href.endswith(".tar.gz") for href in direct_downloads)
    assert any("mags/individual/" in href and href.endswith(".fna.gz") for href in direct_downloads)
    assert any("BGS_BGC_GBK_v1.0.tar.gz" in href for href in direct_downloads)
    assert any("BGS_BGC_proteins_v1.0.faa" in href for href in direct_downloads)
    assert any("BGS_structures_" in href and href.endswith(".tar.gz") for href in direct_downloads)


def test_structure_detail_still_exposes_individual_cif(monkeypatch):
    monkeypatch.setenv("GLOBUS_RELEASE_RELATIVE_ROOT", "staging/v1")
    get_settings.cache_clear()
    response = client.get("/structures/BGS-STR-000001")
    get_settings.cache_clear()

    assert response.status_code == 200
    assert "Download CIF" in response.text
    assert "staging/v1/structures/cif/structures/BGS-STR-000001.cif" in response.text
