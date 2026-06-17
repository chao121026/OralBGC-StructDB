from __future__ import annotations

import json
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import HTTPException

from app.config import get_settings


class UnsafeResourcePath(ValueError):
    pass


def resource_for_entity(entity_type: str, accession: str) -> dict[str, Any] | None:
    for row in _resources():
        if row.get("entity_type") == entity_type and row.get("entity_accession") == accession:
            return _public_resource(row)
    return None


def resources_by_type(resource_type: str) -> list[dict[str, Any]]:
    return [
        _public_resource(row)
        for row in _resources()
        if row.get("resource_type") == resource_type or row.get("resource_category") == resource_type
    ]


def first_resource_by_type(resource_type: str) -> dict[str, Any] | None:
    items = resources_by_type(resource_type)
    return items[0] if items else None


def resources_by_types(resource_types: set[str]) -> list[dict[str, Any]]:
    return [
        _public_resource(row)
        for row in _resources()
        if row.get("resource_type") in resource_types or row.get("resource_category") in resource_types
    ]


def direct_url(relative_path: str, *, browser_fetch: bool = False) -> str:
    settings = get_settings()
    base = settings.globus_browser_fetch_base_url if browser_fetch else settings.globus_direct_https_base_url
    if not base:
        raise HTTPException(status_code=503, detail="Direct resource host is not configured")
    _validate_base(base)
    try:
        root = _safe_relative_path(settings.globus_release_relative_root)
        path = _safe_relative_path(relative_path)
    except UnsafeResourcePath as exc:
        raise HTTPException(status_code=503, detail="Direct resource path is unavailable") from exc
    encoded = "/".join(quote(part, safe="") for part in f"{root}/{path}".split("/"))
    return f"{base.rstrip('/')}/{encoded}"


def _public_resource(row: dict[str, Any]) -> dict[str, Any]:
    relative_path = row.get("relative_path") or ""
    return {
        "filename": row.get("filename") or PurePosixPath(relative_path).name,
        "size_bytes": row.get("size_bytes"),
        "sha256": row.get("sha256") or "",
        "release_version": row.get("release_version") or "",
        "validation_status": row.get("validation_status") or "",
        "resource_type": row.get("resource_type") or row.get("resource_category") or row.get("category") or "",
        "resource_category": row.get("resource_category") or row.get("category") or "",
        "download_url": direct_url(relative_path),
        "browser_fetch_url": direct_url(relative_path, browser_fetch=True),
    }


def _validate_base(base: str) -> None:
    settings = get_settings()
    parsed = urlparse(base)
    allowed_hosts = settings.globus_allowed_hosts or (parsed.netloc,)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise HTTPException(status_code=503, detail="Direct resource host is misconfigured")
    if parsed.netloc not in allowed_hosts or parsed.netloc == "app.globus.org":
        raise HTTPException(status_code=503, detail="Direct resource host is not approved")


def _safe_relative_path(path: str) -> str:
    if not path or "\\" in path or "?" in path or "#" in path or "\x00" in path:
        raise UnsafeResourcePath("Unsafe relative path")
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise UnsafeResourcePath("Unsafe relative path")
    clean = path.strip("/")
    parts = PurePosixPath(clean).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise UnsafeResourcePath("Unsafe relative path")
    return "/".join(parts)


@lru_cache(maxsize=1)
def _resources() -> tuple[dict[str, Any], ...]:
    manifest = get_settings().resolve_manifest()
    with manifest.open() as handle:
        payload = json.load(handle)
    return tuple(payload.get("resources", []))
