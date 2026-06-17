from fastapi.testclient import TestClient
from bs4 import BeautifulSoup
from starlette.requests import Request

from app.config import get_settings
from app.main import app
from app.routes import pages
from app.templates_env import templates


client = TestClient(app)
HERO_AFFILIATION = "Developed at the Public Health Research Center, New York University Abu Dhabi."


def visible_body_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body or soup
    for hidden in body.find_all(["script", "style", "template"]):
        hidden.decompose()
    text = " ".join(body.get_text(" ", strip=True).split())
    return text.replace(" .", ".")


def test_pages_use_shared_template_object_with_branding_context_processor():
    assert pages.templates is templates
    assert len(templates.context_processors) >= 1


def test_homepage_uses_configured_public_branding_and_phrc_link():
    brand = get_settings().branding
    response = client.get("/")

    assert response.status_code == 200
    assert brand["public_name"] in response.text
    assert brand["subtitle"] in response.text
    assert "Public Health Research Center" in response.text
    assert brand["institution_url"] in response.text
    assert 'target="_blank"' in response.text
    assert 'rel="noopener noreferrer"' in response.text


def test_homepage_has_one_visible_hero_affiliation_and_no_global_repeats():
    response = client.get("/")
    soup = BeautifulSoup(response.text, "html.parser")
    body_text = visible_body_text(response.text)
    header_text = soup.select_one("header").get_text(" ", strip=True)
    footer_text = soup.select_one("footer").get_text(" ", strip=True)

    assert body_text.count(HERO_AFFILIATION) == 1
    assert HERO_AFFILIATION not in header_text
    assert HERO_AFFILIATION not in footer_text
    assert "NYU Abu Dhabi PHRC" not in header_text
    assert "NYU Abu Dhabi PHRC" not in body_text
    assert "Public academic resource" in footer_text


def test_about_contact_help_and_footer_include_institutional_context():
    for path in ["/about", "/contact", "/help"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "Public Health Research Center" in response.text
        assert "New York University Abu Dhabi" in response.text

    footer_html = client.get("/").text
    assert "Developed at the Public Health Research Center, New York University Abu Dhabi" in footer_html
    assert "official NYUAD database" not in footer_html


def test_institutional_context_is_not_repeated_on_help_or_detail_pages():
    about_text = visible_body_text(client.get("/about").text)
    contact_text = visible_body_text(client.get("/contact").text)

    assert "Institutional context" in about_text
    assert "Institutional information" in contact_text
    assert HERO_AFFILIATION not in contact_text

    for path in ["/help", "/proteins/BGS-PRT-000001"]:
        response = client.get(path)
        assert response.status_code == 200
        assert HERO_AFFILIATION not in visible_body_text(response.text)


def test_404_page_renders_branded_base_template():
    response = client.get("/definitely-not-real")

    assert response.status_code == 404
    assert "OralBGC-StructDB" in response.text
    assert "Public Health Research Center" in response.text


def test_500_template_renders_when_brand_global_is_unavailable():
    original = templates.env.globals.pop("brand", None)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test-error",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
            "client": ("testclient", 50000),
            "app": app,
        }
    )
    try:
        response = templates.TemplateResponse(
            request=request,
            name="errors/500.html",
            context={},
            status_code=500,
        )
        body = response.body.decode()
    finally:
        if original is not None:
            templates.env.globals["brand"] = original

    assert response.status_code == 500
    assert "OralBGC-StructDB" in body
    assert "Public Health Research Center" in body


def test_metadata_and_json_ld_use_public_display_name_without_paths():
    brand = get_settings().branding
    response = client.get("/")

    assert f"<title>{brand['public_name']}" in response.text
    assert 'property="og:title"' in response.text
    assert 'application/ld+json' in response.text
    assert brand["public_name"] in response.text
    assert "/Users/" not in response.text
    assert "/scratch/" not in response.text


def test_branding_does_not_change_accession_routes_or_legacy_redirects():
    assert client.get("/mags/BGS-MAG-000001").status_code == 200
    assert client.get("/bgcs/BGS-BGC-000001").status_code == 200
    assert client.get("/proteins/BGS-PRT-000001").status_code == 200
    assert client.get("/structures/BGS-STR-000001").status_code == 200

    cif = client.get("/structures/cif/BGS-STR-000001")
    assert cif.status_code == 200
    assert cif.headers["content-type"].startswith("chemical/x-cif")

    legacy = "/bgcs/CH_NA0008303945_S123_metawrap_50_10_bins_metawrap_50_10_bins_bin.4_CH_NA0008303945_S123_contig_138_region001"
    redirect = client.get(legacy, follow_redirects=False)
    assert redirect.status_code == 308
    assert redirect.headers["location"] == "/bgcs/BGS-BGC-000001"


def test_api_accession_fields_are_unchanged_by_branding():
    protein = client.get("/api/proteins", params={"page_size": 1}).json()["items"][0]

    assert protein["protein_accession"].startswith("BGS-PRT-")
    assert protein["bgc_accession"].startswith("BGS-BGC-")
    assert protein["structure_accession"].startswith("BGS-STR-")
    assert protein["original_protein_id"]
