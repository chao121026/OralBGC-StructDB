from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from app.queries import paged_table, get_one_by_public_id
from app.services.stats import stats_payload, chart_payload
from app.services.downloads import list_downloads
from app.services.bigscape import bigscape_summary
from app.services.bigscape_networks import gcf_network, list_networks, network_json
from app.config import get_settings
from app.database import db_connect, table_exists
from app.services.entities import (
    grouped_search,
    get_bgc_detail,
    get_gcf_detail,
    get_mag_detail,
    list_bgcs,
    list_gcfs,
    list_mags,
    list_structures,
)

router=APIRouter(prefix='/api', tags=['api'])

@router.get('/health', summary='Application health')
def health():
    return {"status": "ok", "database": "available", "deployment_mode": get_settings().deployment_mode}

@router.get('/version')
def version():
    with db_connect() as conn:
        metadata = {}
        if table_exists(conn, "database_metadata"):
            metadata = {r._mapping["key"]: r._mapping["value"] for r in conn.execute(text("select key, value from database_metadata"))}
    return {
        "database_version": metadata.get("version", "PHRC_BGCStructDB_v1"),
        "dataset_version": "PHRC initial public release",
        "schema_version": "public-sqlite-v2",
        "ingestion_date": metadata.get("ingested_at"),
        "loaded_datasets": [metadata.get("dataset", "PHRC")],
        "release_root_config": "PHRC_BGCSTRUCTDB_DATA_ROOT",
        "public_name": get_settings().public_name,
        "institution": get_settings().institution,
        "public_base": "read-only public API",
    }

@router.get('/stats')
def stats(): return stats_payload()

@router.get('/charts')
def charts(): return chart_payload()

@router.get('/bigscape/summary')
def bigscape_summary_api():
    payload = bigscape_summary()
    return {key: value for key, value in payload.items() if key != "downloads"}

@router.get('/bigscape/classes')
def bigscape_classes_api():
    return {"items": bigscape_summary()["classes"]}

@router.get('/bigscape/networks')
def bigscape_networks_api():
    return list_networks()

@router.get('/bigscape/networks/{network_id}')
def bigscape_network_api(network_id: str):
    return network_json(network_id)

@router.get('/bigscape/gcfs/{gcf_accession}/network')
def bigscape_gcf_network_api(gcf_accession: str):
    return gcf_network(gcf_accession)

@router.get('/proteins')
def proteins(page:int=1, page_size:int=25, sort_by:str='public_protein_id', sort_dir:str='asc', q:str|None=None, length_bucket:str|None=None, compactness_class:str|None=None, pdb_structural_match_category:str|None=None):
    return paged_table('bgc_protein_summary', page, page_size, sort_by, sort_dir, q, {"length_bucket":length_bucket,"compactness_class":compactness_class,"pdb_structural_match_category":pdb_structural_match_category})

@router.get('/proteins/{public_protein_id:path}')
def protein(public_protein_id: str):
    row=get_one_by_public_id('bgc_protein_summary','public_protein_id',public_protein_id)
    if not row: raise HTTPException(404, 'Protein not found')
    return row

@router.get('/structures')
def structures(page:int=1, page_size:int=25, sort_by:str='public_protein_id', sort_dir:str='asc', q:str|None=None, length_bucket:str|None=None, af3_qc_available:str|None=None, foldseek_annotation_available:str|None=None):
    return list_structures(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir, q=q, length_bucket=length_bucket, af3_qc_available=af3_qc_available, foldseek_annotation_available=foldseek_annotation_available)

@router.get('/downloads')
def downloads(): return {"items": list_downloads()}

@router.get('/columns')
def columns():
    with db_connect() as conn:
        if not table_exists(conn,'column_dictionary'): return {"items": []}
        return {"items": [dict(r._mapping) for r in conn.execute(text('select * from column_dictionary order by column'))]}

@router.get('/search')
def search(q: str = Query('', min_length=0), page_size:int=10):
    return grouped_search(q, page_size)

@router.get('/mags')
def mags(page:int=1, page_size:int=25, sort_by:str='public_mag_id', sort_dir:str='asc', q:str|None=None, dataset:str|None=None):
    return list_mags(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir, q=q, dataset=dataset)

@router.get('/mags/{public_mag_id:path}')
def mag(public_mag_id: str):
    return get_mag_detail(public_mag_id)["record"]

@router.get('/bgcs')
def bgcs(page:int=1, page_size:int=25, sort_by:str='public_bgc_id', sort_dir:str='asc', q:str|None=None, dataset:str|None=None, mag:str|None=None, gcf:str|None=None, bgc_class:str|None=None, assigned:str|None=None):
    return list_bgcs(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir, q=q, dataset=dataset, mag=mag, gcf=gcf, bgc_class=bgc_class, assigned=assigned)

@router.get('/bgcs/{public_bgc_id:path}')
def bgc(public_bgc_id: str):
    return get_bgc_detail(public_bgc_id)["record"]

@router.get('/gcfs')
def gcfs(page:int=1, page_size:int=25, sort_by:str='public_gcf_id', sort_dir:str='asc', q:str|None=None, dataset:str|None=None, bgc_class:str|None=None):
    return list_gcfs(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir, q=q, dataset=dataset, bgc_class=bgc_class)

@router.get('/gcfs/{public_gcf_id:path}')
def gcf(public_gcf_id: str):
    return get_gcf_detail(public_gcf_id)["record"]
