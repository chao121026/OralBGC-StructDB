import os
import urllib.request

import pytest

from app.config import get_settings
from app.services.public_resources import resource_for_entity


pytestmark = pytest.mark.skipif(
    os.getenv("ORALBGC_LIVE_STAGING_VIEWER") != "1",
    reason="live staging viewer test requires ORALBGC_LIVE_STAGING_VIEWER=1",
)


def test_live_staging_cif_url_is_cors_fetchable(monkeypatch):
    monkeypatch.setenv("GLOBUS_RELEASE_RELATIVE_ROOT", "staging/v1")
    get_settings.cache_clear()
    resource = resource_for_entity("structures", "BGS-STR-000001")
    get_settings.cache_clear()

    assert resource is not None
    url = resource["browser_fetch_url"]
    assert url == "https://g-f2d91c.6d8b.03c0.data.globus.org/staging/v1/structures/cif/structures/BGS-STR-000001.cif"
    assert "app.globus.org" not in url

    request = urllib.request.Request(
        url,
        headers={
            "Origin": "http://127.0.0.1:8101",
            "Range": "bytes=0-4095",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
        assert response.status in {200, 206}
        assert response.headers.get("Access-Control-Allow-Origin") in {"*", "http://127.0.0.1:8101"}
        assert response.headers.get("Content-Type", "").startswith("chemical/x-cif")
        assert response.url == url

    assert body.strip()
    assert "data_" in body
    assert not body.lstrip().startswith("<")
    assert "app.globus.org" not in body
