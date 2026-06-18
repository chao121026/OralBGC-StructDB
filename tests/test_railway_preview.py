import json
import sqlite3
import tomllib

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import db_connect
from app.main import app
from app.services.public_resources import direct_url, resource_for_entity


client = TestClient(app)


def test_root_health_endpoint_is_safe_and_railway_ready(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "editor_preview")
    get_settings.cache_clear()
    response = client.get("/health")
    get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "available",
        "deployment_mode": "editor_preview",
    }
    forbidden = ["phrc_bgcstructdb.sqlite", "/Users/", "GLOBUS", "g-f2d91c", "fd17ec48"]
    assert all(token not in response.text for token in forbidden)


def test_railway_start_command_uses_direct_uvicorn():
    expected = 'uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers'

    assert expected in json.loads(open("railway.json").read())["deploy"]["startCommand"]
    assert open("Procfile").read().strip() == f"web: {expected}"
    assert tomllib.loads(open("nixpacks.toml", "rb").read().decode())["start"]["cmd"] == expected


def test_runtime_resource_manifest_is_packaged_and_sanitized():
    settings = get_settings()
    manifest = settings.resolve_manifest()

    assert manifest.as_posix().endswith("app/data/integrated-resource-manifest.json")
    assert manifest.exists()

    payload = json.loads(manifest.read_text())
    assert payload["resources"]
    forbidden_keys = {
        "collection_url",
        "release_collection_url",
        "direct_download_url",
        "browser_fetch_url",
        "resource_id",
        "availability_mode",
        "cors_validated",
        "direct_https_validated",
    }
    allowed_keys = {
        "entity_accession",
        "entity_type",
        "filename",
        "relative_path",
        "release_version",
        "resource_category",
        "resource_type",
        "sha256",
        "size_bytes",
        "validation_status",
    }
    for row in payload["resources"]:
        assert set(row) <= allowed_keys
        assert not (set(row) & forbidden_keys)
        rendered = json.dumps(row)
        assert "/Users/" not in rendered
        assert "/scratch/" not in rendered
        assert "/archive/" not in rendered
        assert "app.globus.org" not in rendered
        assert "fd17ec48" not in rendered


def test_bundled_sqlite_database_rejects_writes():
    with db_connect() as conn:
        with pytest.raises((sqlite3.OperationalError, OperationalError)):
            conn.execute(text("create table milestone6f_write_probe (id integer)"))


def test_editor_preview_banner(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "editor_preview")
    get_settings.cache_clear()
    response = client.get("/")
    get_settings.cache_clear()

    assert response.status_code == 200
    assert "Editorial preview. The permanent release URL and final data publication path will be finalized before public release." not in response.text


def test_direct_mag_resource_url_uses_configured_preview_root(monkeypatch):
    monkeypatch.setenv("GLOBUS_RELEASE_RELATIVE_ROOT", "staging/v1")
    get_settings.cache_clear()
    resource = resource_for_entity("mags", "BGS-MAG-000283")
    get_settings.cache_clear()

    assert resource
    assert resource["download_url"].startswith("https://g-f2d91c.6d8b.03c0.data.globus.org/staging/v1/mags/individual/")
    assert resource["filename"] == "BGS-MAG-000283.fna.gz"
    assert resource["sha256"]
    assert resource["validation_status"] == "validated_hpc"


def test_direct_structure_url_and_viewer_configuration(monkeypatch):
    monkeypatch.setenv("GLOBUS_RELEASE_RELATIVE_ROOT", "staging/v1")
    get_settings.cache_clear()
    response = client.get("/structures/BGS-STR-000001")
    get_settings.cache_clear()

    assert response.status_code == 200
    assert "/static/vendor/3dmol/2.4.2/3Dmol-min.js" in response.text
    assert "https://3Dmol.org" not in response.text
    assert 'data-cif="https://g-f2d91c.6d8b.03c0.data.globus.org/staging/v1/structures/cif/structures/BGS-STR-000001.cif"' in response.text
    assert "Download CIF" in response.text
    assert "fd17ec48-4dcc-4389-88ab-253eabf0eb40" not in response.text
    assert "app.globus.org" not in response.text


def test_bgc_and_protein_pages_are_bulk_only():
    bgc = client.get("/bgcs/BGS-BGC-000890")
    protein = client.get("/proteins/BGS-PRT-000001")

    assert bgc.status_code == 200
    assert "Download BGC archive" in bgc.text
    assert "Individual GenBank downloads are not available in this release." in bgc.text
    assert "/bgcs/gbk/" not in bgc.text

    assert protein.status_code == 200
    assert "Download complete protein FASTA" in protein.text
    assert "Individual protein FASTA downloads are not available in this release." in protein.text


def test_direct_url_rejects_unsafe_paths_and_hosts(monkeypatch):
    with pytest.raises(HTTPException):
        direct_url("../secret.txt")
    with pytest.raises(HTTPException):
        direct_url("structures/cif/file.cif?token=secret")

    monkeypatch.setenv("GLOBUS_DIRECT_HTTPS_BASE_URL", "https://app.globus.org")
    get_settings.cache_clear()
    with pytest.raises(HTTPException):
        direct_url("structures/cif/file.cif")
    get_settings.cache_clear()
