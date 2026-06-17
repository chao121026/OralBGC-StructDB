from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.database import db_connect
from app.services.downloads import list_downloads


NETWORK_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
BGC_RE = re.compile(r"^BGS-BGC-\d{6}$")
GCF_RE = re.compile(r"^BGS-GCF-C03-\d{4}$")


@dataclass(frozen=True)
class NetworkManifestEntry:
    network_id: str
    cutoff: str
    bigscape_class: str
    node_count: int
    edge_count: int
    mapped_node_count: int
    unmapped_node_count: int
    mapped_edge_count: int
    malformed_rows: int
    size_bytes: int
    sha256: str
    public_safe: bool
    status: str
    notes: str
    public_relative_path: str
    json_relative_path: str
    renderable: bool
    render_block_reason: str
    mapping_complete: bool
    download_key: str | None


def list_networks() -> dict:
    entries = _manifest_entries()
    return {
        "limits": _limits(),
        "items": [_public_entry(entry) for entry in entries],
        "renderable_count": sum(1 for entry in entries if entry.renderable),
        "download_only_count": sum(1 for entry in entries if not entry.renderable),
    }


def network_json(network_id: str) -> dict:
    entry = _entry_by_id(network_id)
    if not entry.public_safe:
        raise HTTPException(status_code=404, detail={"message": "Network is not public allowlisted."})
    if not entry.renderable:
        raise HTTPException(status_code=413, detail={"message": "Network exceeds the interactive viewer size limit.", "network": _public_entry(entry)})
    payload = _build_network_payload(entry)
    _enforce_response_size(payload)
    return payload


def gcf_network(gcf_accession: str) -> dict:
    if not GCF_RE.fullmatch(gcf_accession):
        raise HTTPException(status_code=400, detail="Invalid GCF accession")
    gcf = _gcf_metadata(gcf_accession)
    if not gcf:
        raise HTTPException(status_code=404, detail="GCF not found")
    members = _bgc_metadata_for_gcf(gcf_accession)
    member_ids = {row["bgc_accession"] for row in members}
    if len(member_ids) > get_settings().bigscape_max_nodes:
        raise HTTPException(status_code=413, detail={"message": "GCF exceeds the interactive viewer node limit."})
    entry = _primary_entry_for_class(gcf["bigscape_class"])
    edges = []
    if entry:
        for edge in _read_edges(entry):
            if edge["source"] in member_ids and edge["target"] in member_ids:
                edges.append(edge)
                if len(edges) > get_settings().bigscape_max_edges:
                    raise HTTPException(status_code=413, detail={"message": "GCF exceeds the interactive viewer edge limit."})
    nodes = [_cy_node(row) for row in members]
    node_ids = {node["data"]["id"] for node in nodes}
    cy_edges = [_cy_edge(edge, index) for index, edge in enumerate(edges, start=1) if edge["source"] in node_ids and edge["target"] in node_ids]
    payload = {
        "metadata": {
            "source": "gcf",
            "gcf_accession": gcf_accession,
            "bigscape_class": gcf["bigscape_class"],
            "cutoff": "0.3",
            "network_id": entry.network_id if entry else None,
            "node_count": len(nodes),
            "edge_count": len(cy_edges),
            "renderable": True,
            "singleton": len(nodes) == 1,
            "warnings": [] if entry else ["No primary c0.3 class network file is available for this GCF class."],
        },
        "elements": {"nodes": nodes, "edges": cy_edges},
    }
    _enforce_response_size(payload)
    return payload


def default_gcf_accession() -> str | None:
    with db_connect() as conn:
        row = conn.execute(text("""
            select public_gcf_id
            from bigscape_gcf_summary
            where coalesce(public_gcf_id, '') != ''
            order by cast(number_BGCs as integer) desc, public_gcf_id
            limit 1
        """)).first()
    return row[0] if row else None


def write_network_json_files(output_root: Path | None = None) -> list[Path]:
    root = output_root or (_release_bigscape_root() / "public" / "networks" / "json")
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for entry in _manifest_entries():
        if not entry.renderable:
            continue
        path = root / f"{entry.network_id}.json"
        path.write_text(json.dumps(_build_network_payload(entry), separators=(",", ":")) + "\n")
        written.append(path)
    return written


def _limits() -> dict:
    settings = get_settings()
    return {
        "max_nodes": settings.bigscape_max_nodes,
        "max_edges": settings.bigscape_max_edges,
        "max_json_bytes": settings.bigscape_max_json_bytes,
    }


@lru_cache(maxsize=1)
def _manifest_entries() -> tuple[NetworkManifestEntry, ...]:
    manifest = _release_bigscape_root() / "public" / "networks" / "network_file_manifest.tsv"
    if not manifest.exists():
        return ()
    download_keys = _download_keys()
    entries = []
    with manifest.open(newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            entries.append(_entry_from_row(row, download_keys))
    return tuple(sorted(entries, key=lambda entry: (entry.cutoff != "0.3", entry.cutoff, entry.bigscape_class, entry.network_id)))


def _entry_from_row(row: dict[str, str], download_keys: dict[str, str]) -> NetworkManifestEntry:
    public_relative_path = row.get("public_relative_path", "")
    network_id = row.get("network_id") or _network_id(public_relative_path)
    mapped_node_count = _int(row.get("mapped_node_count"))
    mapped_edge_count = _int(row.get("mapped_edge_count"))
    public_safe = row.get("public_safe") == "true"
    renderable, reason = _renderable(public_safe, mapped_node_count, mapped_edge_count)
    cutoff = row.get("cutoff") or ""
    archive = "bigscape_primary_c0.3_networks.tar.gz" if cutoff == "0.3" else "bigscape_alternative_cutoff_networks.tar.gz"
    return NetworkManifestEntry(
        network_id=network_id,
        cutoff=cutoff,
        bigscape_class=row.get("bigscape_class") or "",
        node_count=_int(row.get("node_count")),
        edge_count=_int(row.get("edge_count")),
        mapped_node_count=mapped_node_count,
        unmapped_node_count=_int(row.get("unmapped_node_count")),
        mapped_edge_count=mapped_edge_count,
        malformed_rows=_int(row.get("malformed_rows")),
        size_bytes=_int(row.get("size_bytes")),
        sha256=row.get("sha256") or "",
        public_safe=public_safe,
        status=row.get("status") or "",
        notes=row.get("notes") or "",
        public_relative_path=public_relative_path,
        json_relative_path=row.get("json_relative_path") or f"public/networks/json/{network_id}.json",
        renderable=renderable,
        render_block_reason=reason,
        mapping_complete=_int(row.get("unmapped_node_count")) == 0,
        download_key=download_keys.get(archive),
    )


def _network_id(public_relative_path: str) -> str:
    path = Path(public_relative_path)
    parent = path.parent.name.replace(".", "p")
    stem = path.name.removesuffix("_bgs_edges.tsv").replace(".", "p")
    network_id = f"{parent}-{stem}"
    if not NETWORK_ID_RE.fullmatch(network_id):
        raise HTTPException(status_code=500, detail="Invalid allowlisted network id")
    return network_id


def _renderable(public_safe: bool, mapped_nodes: int, mapped_edges: int) -> tuple[bool, str]:
    settings = get_settings()
    if not public_safe:
        return False, "not_public_safe"
    if mapped_nodes > settings.bigscape_max_nodes:
        return False, "node_limit"
    if mapped_edges > settings.bigscape_max_edges:
        return False, "edge_limit"
    return True, ""


def _entry_by_id(network_id: str) -> NetworkManifestEntry:
    if not NETWORK_ID_RE.fullmatch(network_id) or "/" in network_id or "\\" in network_id or "\x00" in network_id:
        raise HTTPException(status_code=400, detail="Invalid network id")
    for entry in _manifest_entries():
        if entry.network_id == network_id:
            return entry
    raise HTTPException(status_code=404, detail="Network not found")


def _primary_entry_for_class(bigscape_class: str) -> NetworkManifestEntry | None:
    for entry in _manifest_entries():
        if entry.cutoff == "0.3" and entry.bigscape_class == bigscape_class and entry.public_safe:
            return entry
    return None


def _public_entry(entry: NetworkManifestEntry) -> dict:
    download_url = None
    if entry.download_key:
        download_url = next(
            (item["download_url"] for item in list_downloads() if item.get("file_key") == entry.download_key),
            None,
        )
    return {
        "network_id": entry.network_id,
        "cutoff": entry.cutoff,
        "class": entry.bigscape_class,
        "node_count": entry.node_count,
        "edge_count": entry.edge_count,
        "mapped_node_count": entry.mapped_node_count,
        "unmapped_node_count": entry.unmapped_node_count,
        "mapped_edge_count": entry.mapped_edge_count,
        "malformed_rows": entry.malformed_rows,
        "size_bytes": entry.size_bytes,
        "sha256": entry.sha256,
        "public_safe": entry.public_safe,
        "mapping_complete": entry.mapping_complete,
        "renderable": entry.renderable,
        "render_block_reason": entry.render_block_reason,
        "download_key": entry.download_key,
        "download_url": download_url,
    }


def _build_network_payload(entry: NetworkManifestEntry) -> dict:
    edges = list(_read_edges(entry))
    node_ids = sorted({edge["source"] for edge in edges} | {edge["target"] for edge in edges})
    metadata = _bgc_metadata(node_ids)
    nodes = [_cy_node(metadata[node_id]) for node_id in node_ids if node_id in metadata]
    valid_node_ids = {node["data"]["id"] for node in nodes}
    cy_edges = [_cy_edge(edge, index) for index, edge in enumerate(edges, start=1) if edge["source"] in valid_node_ids and edge["target"] in valid_node_ids]
    payload = {
        "metadata": {
            "source": "network",
            "network_id": entry.network_id,
            "cutoff": entry.cutoff,
            "bigscape_class": entry.bigscape_class,
            "node_count": len(nodes),
            "edge_count": len(cy_edges),
            "original_node_count": entry.node_count,
            "original_edge_count": entry.edge_count,
            "mapped_node_count": entry.mapped_node_count,
            "unmapped_node_count": entry.unmapped_node_count,
            "mapped_edge_count": entry.mapped_edge_count,
            "mapping_complete": entry.mapping_complete,
            "renderable": entry.renderable,
            "edge_metric": "distance",
            "edge_metric_note": "BiG-SCAPE distance is preserved from the mapped public edge list; values are not inverted.",
        },
        "elements": {"nodes": nodes, "edges": cy_edges},
    }
    return payload


def _read_edges(entry: NetworkManifestEntry):
    path = _public_file(entry.public_relative_path)
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            source = row.get("source_bgc_accession") or ""
            target = row.get("target_bgc_accession") or ""
            if not BGC_RE.fullmatch(source) or not BGC_RE.fullmatch(target):
                continue
            yield {
                "source": source,
                "target": target,
                "distance": row.get("distance") or "",
                "jaccard": row.get("jaccard") or "",
                "adjacency": row.get("adjacency") or "",
                "dss": row.get("dss") or "",
                "original_source_id": row.get("original_source_id") or "",
                "original_target_id": row.get("original_target_id") or "",
            }


def _cy_node(row: dict) -> dict:
    return {
        "data": {
            "id": row["bgc_accession"],
            "label": row["bgc_accession"],
            "bgc_accession": row["bgc_accession"],
            "gcf_accession": row.get("gcf_accession") or "",
            "mag_accession": row.get("mag_accession") or "",
            "bigscape_class": row.get("bigscape_class") or "",
            "protein_count": row.get("protein_count") or 0,
            "structure_count": row.get("structure_count") or 0,
            "original_bgc_id": row.get("original_bgc_id") or "",
            "bgc_url": f"/bgcs/{row['bgc_accession']}",
        }
    }


def _cy_edge(edge: dict, index: int) -> dict:
    data = {
        "id": f"edge-{index:06d}",
        "source": edge["source"],
        "target": edge["target"],
    }
    for key in ["distance", "jaccard", "adjacency", "dss", "original_source_id", "original_target_id"]:
        if edge.get(key) != "":
            data[key] = edge[key]
    return {"data": data}


def _bgc_metadata(public_bgc_ids: list[str]) -> dict[str, dict]:
    if not public_bgc_ids:
        return {}
    rows = {}
    with db_connect() as conn:
        for batch in _batches(public_bgc_ids, 500):
            placeholders = ", ".join(f":id{i}" for i in range(len(batch)))
            params = {f"id{i}": value for i, value in enumerate(batch)}
            query = text(f"""
                select b.public_bgc_id as bgc_accession,
                       b.public_gcf_id as gcf_accession,
                       b.public_mag_id as mag_accession,
                       b.bigscape_class_primary as bigscape_class,
                       b.number_BGC_proteins as protein_count,
                       b.original_bgc_id as original_bgc_id,
                       coalesce(p.structure_count, 0) as structure_count
                from bgc_summary b
                left join (
                  select public_bgc_id, sum(case when structure_available='1' then 1 else 0 end) as structure_count
                  from bgc_protein_summary
                  where public_bgc_id in ({placeholders})
                  group by public_bgc_id
                ) p using(public_bgc_id)
                where b.public_bgc_id in ({placeholders})
            """)
            for row in conn.execute(query, params):
                item = dict(row._mapping)
                item["protein_count"] = _int(item.get("protein_count"))
                item["structure_count"] = _int(item.get("structure_count"))
                rows[item["bgc_accession"]] = item
    return rows


def _bgc_metadata_for_gcf(gcf_accession: str) -> list[dict]:
    with db_connect() as conn:
        rows = [dict(row._mapping) for row in conn.execute(text("""
            select b.public_bgc_id as bgc_accession,
                   b.public_gcf_id as gcf_accession,
                   b.public_mag_id as mag_accession,
                   b.bigscape_class_primary as bigscape_class,
                   b.number_BGC_proteins as protein_count,
                   b.original_bgc_id as original_bgc_id,
                   coalesce(p.structure_count, 0) as structure_count
            from bgc_summary b
            left join (
              select public_bgc_id, sum(case when structure_available='1' then 1 else 0 end) as structure_count
              from bgc_protein_summary
              group by public_bgc_id
            ) p using(public_bgc_id)
            where b.public_gcf_id = :gcf
            order by b.public_bgc_id
        """), {"gcf": gcf_accession})]
    for row in rows:
        row["protein_count"] = _int(row.get("protein_count"))
        row["structure_count"] = _int(row.get("structure_count"))
    return rows


def _gcf_metadata(gcf_accession: str) -> dict | None:
    with db_connect() as conn:
        row = conn.execute(text("""
            select public_gcf_id as gcf_accession,
                   bigscape_class_primary as bigscape_class,
                   number_BGCs as node_count,
                   number_MAGs as mag_count
            from bigscape_gcf_summary
            where public_gcf_id = :gcf
        """), {"gcf": gcf_accession}).mappings().first()
    return dict(row) if row else None


def _public_file(relative_path: str) -> Path:
    if "\x00" in relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise HTTPException(status_code=500, detail="Unsafe public network path")
    root = _release_bigscape_root()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Unsafe public network path") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Network file not found")
    return path


def _release_bigscape_root() -> Path:
    return get_settings().resolve_package_root() / "bigscape"


def _download_keys() -> dict[str, str]:
    return {item["filename"]: item["file_key"] for item in list_downloads()}


def _enforce_response_size(payload: dict) -> None:
    size = len(json.dumps(payload, separators=(",", ":")).encode())
    if size > get_settings().bigscape_max_json_bytes:
        raise HTTPException(status_code=413, detail={"message": "Network JSON exceeds the interactive viewer response-size limit."})


def _batches(values: list[str], size: int):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
