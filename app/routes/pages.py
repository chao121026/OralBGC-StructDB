from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from app.queries import paged_table, get_one_by_public_id
from app.services.stats import stats_payload, chart_payload, featured_records
from app.services.downloads import list_downloads
from app.database import db_connect, table_exists

templates=Jinja2Templates(directory='app/templates')
router=APIRouter(default_response_class=HTMLResponse)

@router.get('/')
def home(request: Request):
    return templates.TemplateResponse('home.html', {"request":request, "stats":stats_payload(), "charts":chart_payload(), "featured":featured_records(), "active":"home"})

@router.get('/proteins')
def protein_browse(request: Request, page:int=1, page_size:int=25, sort_by:str='public_protein_id', sort_dir:str='asc', q:str|None=None, length_bucket:str|None=None, compactness_class:str|None=None, pdb_structural_match_category:str|None=None):
    data=paged_table('bgc_protein_summary',page,page_size,sort_by,sort_dir,q,{"length_bucket":length_bucket,"compactness_class":compactness_class,"pdb_structural_match_category":pdb_structural_match_category})
    ctx={"request":request,"data":data,"q":q or '',"filters":{"length_bucket":length_bucket or '',"compactness_class":compactness_class or '',"pdb_structural_match_category":pdb_structural_match_category or ''},"active":"proteins"}
    tmpl='partials/protein_table.html' if request.headers.get('hx-request') else 'browse/proteins.html'
    return templates.TemplateResponse(tmpl, ctx)

@router.get('/proteins/{public_protein_id:path}')
def protein_detail(request: Request, public_protein_id: str):
    protein=get_one_by_public_id('bgc_protein_summary','public_protein_id',public_protein_id)
    if not protein: raise HTTPException(404, 'Protein not found')
    with db_connect() as conn:
        related=[]
        if table_exists(conn,'bgc_protein_summary'):
            related=[dict(r._mapping) for r in conn.execute(text('select public_protein_id, query, product, mean_plddt, pdb_structural_match_category from bgc_protein_summary where bgc_id=:b and public_protein_id != :p limit 8'), {"b":protein.get('bgc_id'),"p":public_protein_id})]
    return templates.TemplateResponse('detail/protein.html', {"request":request,"protein":protein,"related":related,"active":"proteins"})

@router.get('/downloads')
def downloads(request: Request):
    items=list_downloads(); groups={}
    for item in items: groups.setdefault(item['category'], []).append(item)
    return templates.TemplateResponse('downloads.html', {"request":request,"groups":groups,"active":"downloads"})

@router.get('/help')
def help_page(request: Request): return templates.TemplateResponse('help.html', {"request":request,"active":"help"})
@router.get('/about')
def about(request: Request): return templates.TemplateResponse('about.html', {"request":request,"active":"about"})
@router.get('/contact')
def contact(request: Request): return templates.TemplateResponse('contact.html', {"request":request,"active":"contact"})
@router.get('/bgcs')
def bgcs_page(request: Request): return templates.TemplateResponse('placeholder.html', {"request":request,"title":"Browse BGCs","active":"bgcs"})
@router.get('/mags')
def mags_page(request: Request): return templates.TemplateResponse('placeholder.html', {"request":request,"title":"Browse MAGs","active":"mags"})
@router.get('/gcfs')
def gcfs_page(request: Request): return templates.TemplateResponse('placeholder.html', {"request":request,"title":"Browse GCFs","active":"gcfs"})
@router.get('/structures')
def structures_page(request: Request): return templates.TemplateResponse('placeholder.html', {"request":request,"title":"Browse Structures","active":"structures"})
@router.get('/search')
def search_page(request: Request): return templates.TemplateResponse('placeholder.html', {"request":request,"title":"Search","active":"search"})
@router.get('/networks')
def networks_page(request: Request): return templates.TemplateResponse('placeholder.html', {"request":request,"title":"Networks","active":"networks"})
