from fastapi.testclient import TestClient
from bs4 import BeautifulSoup
from starlette.requests import Request

from app.config import get_settings
from app.main import app
from app.routes import pages
from app.templates_env import templates


client = TestClient(app)
HERO_AFFILIATION = "Developed by Public Health Research Center, New York University Abu Dhabi."
OLD_HERO_AFFILIATION = "Developed at the Public Health Research Center, New York University Abu Dhabi."
INTERNAL_RELEASE_SENTENCE = "Internal candidate ranking and IP-development files are excluded from this academic release."
EDITORIAL_PREVIEW_SENTENCE = "Editorial preview. The permanent release URL and final data publication path will be finalized before public release."


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
    hero = soup.select_one(".hero-card")

    assert body_text.count(HERO_AFFILIATION) == 1
    assert OLD_HERO_AFFILIATION not in body_text
    assert HERO_AFFILIATION not in header_text
    assert HERO_AFFILIATION not in footer_text
    assert "NYU Abu Dhabi PHRC" not in header_text
    assert "NYU Abu Dhabi PHRC" not in body_text
    assert "Public academic resource" in footer_text
    assert INTERNAL_RELEASE_SENTENCE not in body_text
    assert hero is not None
    assert hero.select_one(".action-row") is None
    for removed in ["Explore proteins", "Browse BGCs", "Downloads"]:
        assert removed not in hero.get_text(" ", strip=True)
    assert EDITORIAL_PREVIEW_SENTENCE not in body_text


def test_homepage_hero_card_has_left_offset_and_bar_spacing_css():
    css = app.dependency_overrides.get("unused") or open("app/static/css/site.css").read()

    assert "margin-left: clamp(-1.25rem, -1vw, -0.5rem)" in css
    assert "padding-left: clamp(1rem, 2vw, 1.75rem)" in css
    assert "margin-left: 0" in css


def test_homepage_workflow_renders_readable_labels_and_links():
    response = client.get("/")
    soup = BeautifulSoup(response.text, "html.parser")

    assert response.status_code == 200
    workflow = soup.select_one(".workflow-grid")
    assert workflow is not None
    expected_steps = [
        ("1", "MAG", "Genome context", "/mags"),
        ("2", "antiSMASH BGC", "Region calls", "/bgcs"),
        ("3", "BiG-SCAPE GCF", "Primary c0.3 families", "/gcfs"),
        ("4", "BGC protein", "CDS-level records", "/proteins"),
        ("5", "Predicted structure", "CIF availability", "/structures"),
        ("6", "Foldseek/PDB", "Structural annotation", "/structures"),
    ]

    steps = workflow.select(".workflow-step")
    assert len(steps) == len(expected_steps)
    for step, (number, title, subtitle, href) in zip(steps, expected_steps):
        assert step.select_one(".workflow-step-number").get_text(strip=True) == number
        assert step.select_one(".workflow-step-title").get_text(strip=True) == title
        assert step.select_one(".workflow-step-subtitle").get_text(strip=True) == subtitle
        assert step.find("a", href=href) is not None

    assert "antiSMASH BGC" in workflow.get_text(" ", strip=True)
    assert "Predicted structure" in workflow.get_text(" ", strip=True)
    assert "Region calls" in workflow.get_text(" ", strip=True)
    assert "CIF availability" in workflow.get_text(" ", strip=True)
    assert "antiSMASH<br" not in response.text
    assert "Predicted<br" not in response.text
    assert "antiSMASH BGC" in response.text
    assert "Predicted structure" in response.text

    for href in ["/mags", "/bgcs", "/gcfs", "/proteins", "/structures", "/downloads"]:
        assert soup.find("a", href=href) is not None


def test_homepage_workflow_css_uses_wider_responsive_layout():
    css = app.dependency_overrides.get("unused") or open("app/static/css/site.css").read()

    assert ".hero .hero-grid" in css
    assert "max-width: 1440px" in css
    assert "grid-template-columns: minmax(0, 0.68fr) minmax(620px, 1.32fr)" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(min(100%, 11.5rem), 1fr))" in css
    assert "grid-template-rows: auto minmax(2.5rem, auto) auto" in css
    assert ".workflow-step-title" in css
    assert ".workflow-step-subtitle" in css
    assert "overflow-wrap: normal" in css
    assert "word-break: normal" in css
    assert "hyphens: none" in css
    assert ".workflow-step-title--nowrap" in css
    assert "white-space: nowrap" in css


def test_about_contact_help_and_footer_include_institutional_context():
    for path in ["/about", "/contact", "/help"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "Public Health Research Center" in response.text
        assert "New York University Abu Dhabi" in response.text

    footer_html = client.get("/").text
    assert HERO_AFFILIATION in footer_html
    assert OLD_HERO_AFFILIATION not in footer_html
    assert "official NYUAD database" not in footer_html


def test_public_copy_removes_preview_limitations_comparison_and_contact_issue_sections(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "editor_preview")
    get_settings.cache_clear()
    home = client.get("/")
    get_settings.cache_clear()
    help_page = client.get("/help")
    about = client.get("/about")
    contact = client.get("/contact")

    for response in [home, help_page, about, contact]:
        assert response.status_code == 200

    assert EDITORIAL_PREVIEW_SENTENCE not in home.text
    assert "Known limitations" not in help_page.text

    about_soup = BeautifulSoup(about.text, "html.parser")
    about_text = visible_body_text(about.text)
    for removed in ["Limitations", "Comparison", "BGC Atlas", "ABC-HuMi"]:
        assert removed not in about_text
    citation = about_soup.find(id="citation")
    assert citation is not None
    assert citation.find_next("p").get_text(strip=True) == "To be decided"

    contact_text = visible_body_text(contact.text)
    assert "jz7982@nyu.edu" in contact.text
    assert "mailto:jz7982@nyu.edu" in contact.text
    assert "contact@example.edu" not in contact.text
    assert "Broken links and software issues" not in contact_text


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
