from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.main import templates
from app.services.downloads import build_download_page_context


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


def test_downloads_api_exposes_controlled_presentation_metadata():
    client = TestClient(app)
    response = client.get('/api/downloads')
    assert response.status_code == 200
    items = response.json()['items']

    primary = [
        item for item in items
        if item.get('audience_level') == 'recommended'
        and item.get('is_primary')
        and item['filename'].startswith('PHRC_integrated_BGC_protein_structure_summary')
    ]
    assert len(primary) == 1
    assert primary[0]['recommended_label'] == 'Recommended primary metadata table'
    assert primary[0]['record_count'] == 22626

    recommended = [item for item in items if item.get('audience_level') == 'recommended']
    assert recommended
    assert all(item.get('recommended_rank') is not None for item in recommended)
    assert all(item.get('download_url', '').startswith('/downloads/file/') for item in recommended)

    component = next(item for item in items if item['filename'] == 'BGC_protein_summary.tsv')
    assert component['audience_level'] == 'advanced'
    assert component['advanced_group'] == 'Component tables'

    cytoscape = next(item for item in items if item['filename'] == 'cytoscape_files.tar.gz')
    assert cytoscape['audience_level'] == 'advanced'
    assert cytoscape['is_empty'] is True
    assert cytoscape['availability'] == 'unavailable'
    assert cytoscape.get('download_url') is None

    for item in items:
        assert 'relative_path' not in item
        if item.get('download_url'):
            assert item['download_url'].startswith('/downloads/file/')


def test_download_context_always_contains_advanced_groups():
    context = build_download_page_context()
    assert "recommended_downloads" in context
    assert "advanced_groups" in context
    assert "advanced_count" in context
    assert "download_count" in context
    assert isinstance(context["recommended_downloads"], list)
    assert isinstance(context["advanced_groups"], dict)

    primary = [
        item for item in context["recommended_downloads"]
        if item["is_primary"]
        and item["filename"] == "PHRC_integrated_BGC_protein_structure_summary.tsv"
    ]
    assert len(primary) == 1

    cytoscape = [
        item for items in context["advanced_groups"].values()
        for item in items
        if item["filename"] == "cytoscape_files.tar.gz"
    ]
    assert len(cytoscape) == 1
    assert cytoscape[0]["availability"] == "unavailable"
    assert cytoscape[0]["download_url"] is None


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


def test_downloads_page_renders_recommended_exports_and_collapsed_advanced():
    client = TestClient(app)
    response = client.get('/downloads')
    assert response.status_code == 200
    html = response.text

    assert 'Recommended data' in html
    assert 'Record-level and filtered exports' in html
    assert '<details class="advanced-downloads">' in html
    assert '<summary>' in html
    assert 'Recommended primary metadata table' in html
    assert 'PHRC_integrated_BGC_protein_structure_summary.tsv' in html
    assert 'AF3_final_models_short.tar.gz' in html
    assert 'md5sums.txt' in html

    advanced_index = html.index('<details class="advanced-downloads">')
    component_index = html.index('BGC_protein_summary.tsv')
    assert component_index > advanced_index
    assert 'cytoscape_files.tar.gz' in html
    assert 'Unavailable in this release' in html
    assert 'href="/downloads/file/b44b5de0e2b61216"' not in html
    assert '<details class="advanced-downloads">' in html
    assert '<details class="advanced-downloads" open' not in html

    for sensitive in [
        'internal-priority',
        'drug_discovery_ranked_candidates',
        'candidate_peptides',
        'high_priority_candidate_models',
        'candidate_scores',
        'private obesity',
        'commercial annotations',
    ]:
        assert sensitive not in html


def test_downloads_head_request_reports_available_page():
    client = TestClient(app)
    response = client.head('/downloads')
    assert response.status_code == 200


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
    assert 'PHRC|...|region001|cds11' in html
    assert 'PHRC|CM_NA0009364731' in html


def test_custom_jinja_filters_registered():
    for filter_name in ['short_id', 'human_label', 'humanize_label', 'fmt_measure']:
        assert filter_name in templates.env.filters


def test_exact_reported_protein_detail_route_renders():
    client = TestClient(app)
    response = client.get('/proteins/PHRC%7CCH_NA0008303945_S123_metawrap_50_10_bins_metawrap_50_10_bins_bin.4_CH_NA0008303945_S123_contig_138_region001_cds15')
    assert response.status_code == 200
    assert 'PHRC|...|region001|cds15' in response.text


def test_visual_polish_contracts_render():
    client = TestClient(app)

    home = client.get('/').text
    assert 'class="metric-section core-metrics"' in home
    assert 'class="metric-section coverage-metrics"' in home
    assert 'chart-scroll' in home

    proteins = client.get('/proteins').text
    assert '<details class="protein-card-extra">' in proteins
    assert 'data-label="Detail"' in proteins

    protein_id = 'PHRC|CH_NA0008303945_S123_metawrap_50_10_bins_metawrap_50_10_bins_bin.4_CH_NA0008303945_S123_contig_138_region001_cds15'
    detail = client.get('/proteins/' + protein_id).text
    assert 'identifier-row' in detail
    assert 'data-copy-value=' in detail
    assert 'viewer-controls' in detail
    for control in ['Reset', 'Spin', 'Cartoon', 'Surface', 'pLDDT', 'Fullscreen']:
        assert control in detail
