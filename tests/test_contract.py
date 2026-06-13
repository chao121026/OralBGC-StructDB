from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


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
    assert '/scratch/' not in text
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
    assert 'AlphaFold3 CIF viewer' in response.text
