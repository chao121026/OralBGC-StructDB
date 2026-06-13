from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.main import templates


def test_health_endpoint_reports_ok():
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_sensitive_internal_table_not_downloadable():
    client = TestClient(app)
    response = client.get('/api/downloads')
    assert response.status_code == 200
    payload = response.json()
    names = {item['filename'] for item in payload['items']}
    assert 'PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv' not in names


def test_structure_route_rejects_traversal():
    client = TestClient(app)
    response = client.get('/structures/cif/..%2Fsecret')
    assert response.status_code in {400, 404}


def test_protein_api_hides_raw_filesystem_paths():
    client = TestClient(app)
    response = client.get('/api/proteins?page=1&page_size=20')
    assert response.status_code == 200
    text = response.text
    assert f"/{'scratch'}/" not in text
    for item in response.json()['items']:
        assert 'model_cif' not in item
        assert 'region_file' not in item


def test_checkpoint_pages_render():
    client = TestClient(app)
    for path in ['/', '/proteins', '/downloads']:
        response = client.get(path)
        assert response.status_code == 200
    pid = 'PHRC|CM_NA0009364731_S111_metawrap_50_10_bins_metawrap_50_10_bins_bin.14_CM_NA0009364731_S111_contig_247_region001_cds11'
    response = client.get('/proteins/' + pid)
    assert response.status_code == 200
    assert 'Predicted structure viewer' in response.text


def test_homepage_exposes_four_scientific_chart_containers():
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    for chart_id in [
        'chart-bgc-class',
        'chart-confidence',
        'chart-length',
        'chart-pdb-category',
    ]:
        assert chart_id in response.text


def test_mobile_navigation_contract_is_present_and_closed_by_default():
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    html = response.text
    assert 'id="mobile-menu-toggle"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="nav-overlay"' in html
    assert 'js/navigation.js' in html
    assert 'nav-open' not in html


def test_protein_browse_uses_mobile_cards_and_short_identifiers():
    client = TestClient(app)
    response = client.get('/proteins')
    assert response.status_code == 200
    html = response.text
    assert 'data-table mobile-cards' in html
    assert 'data-label="Public protein ID"' in html
    assert 'identifier-cell' in html
    assert 'title="PHRC|' in html


def test_protein_detail_contains_contained_viewer_loading_state_and_short_id():
    client = TestClient(app)
    pid = 'PHRC|CM_NA0009364731_S111_metawrap_50_10_bins_metawrap_50_10_bins_bin.14_CM_NA0009364731_S111_contig_247_region001_cds11'
    response = client.get('/proteins/' + pid)
    assert response.status_code == 200
    html = response.text
    assert 'class="structure-viewer"' in html
    assert 'structure-loading' in html
    assert 'identifier-block' in html
    assert 'region001 · cds11' in html
    assert 'PHRC|CM_NA0009364731' in html


def test_custom_jinja_filters_registered():
    for filter_name in ['short_id', 'human_label', 'humanize_label', 'fmt_measure']:
        assert filter_name in templates.env.filters


def test_exact_reported_protein_detail_route_renders():
    client = TestClient(app)
    response = client.get('/proteins/PHRC%7CCH_NA0008303945_S123_metawrap_50_10_bins_metawrap_50_10_bins_bin.4_CH_NA0008303945_S123_contig_138_region001_cds15')
    assert response.status_code == 200
    assert 'region001 · cds15' in response.text
