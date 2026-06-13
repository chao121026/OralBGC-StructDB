from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from app.queries import paged_table, get_one_by_public_id
from app.services.stats import stats_payload, chart_payload
from app.services.downloads import list_downloads
from app.database import db_connect, table_exists

router=APIRouter(prefix='/api', tags=['api'])

@router.get('/health', summary='Application health')
def health(): return {"status":"ok", "service":"PHRC_BGCStructDB"}

@router.get('/version')
def version(): return {"version":"PHRC_BGCStructDB_v1", "dataset":"PHRC"}

@router.get('/stats')
def stats(): return stats_payload()

@router.get('/charts')
def charts(): return chart_payload()

@router.get('/proteins')
def proteins(page:int=1, page_size:int=25, sort_by:str='public_protein_id', sort_dir:str='asc', q:str|None=None, length_bucket:str|None=None, compactness_class:str|None=None, pdb_structural_match_category:str|None=None):
    return paged_table('bgc_protein_summary', page, page_size, sort_by, sort_dir, q, {"length_bucket":length_bucket,"compactness_class":compactness_class,"pdb_structural_match_category":pdb_structural_match_category})

@router.get('/proteins/{public_protein_id:path}')
def protein(public_protein_id: str):
    row=get_one_by_public_id('bgc_protein_summary','public_protein_id',public_protein_id)
    if not row: raise HTTPException(404, 'Protein not found')
    return row

@router.get('/structures')
def structures(page:int=1, page_size:int=25, sort_by:str='public_protein_id', sort_dir:str='asc', q:str|None=None):
    return paged_table('bgc_protein_summary', page, page_size, sort_by, sort_dir, q, {"dataset":"PHRC"})

@router.get('/downloads')
def downloads(): return {"items": list_downloads()}

@router.get('/columns')
def columns():
    with db_connect() as conn:
        if not table_exists(conn,'column_dictionary'): return {"items": []}
        return {"items": [dict(r._mapping) for r in conn.execute(text('select * from column_dictionary order by column'))]}

@router.get('/search')
def search(q: str = Query('', min_length=0), page_size:int=10):
    result=paged_table('bgc_protein_summary',1,page_size,'public_protein_id','asc',q,{})
    return {"q": q, "groups": {"proteins": result["items"]}, "total": result["total"]}

@router.get('/mags')
def mags(): return paged_table('mag_summary',1,25,None,'asc',None,{})
@router.get('/bgcs')
def bgcs(): return paged_table('bgc_summary',1,25,None,'asc',None,{})
@router.get('/gcfs')
def gcfs(): return paged_table('bigscape_gcf_summary',1,25,None,'asc',None,{})
