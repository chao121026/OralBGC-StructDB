from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import text
from app.queries import paged_table, get_one_by_public_id
from app.services.stats import stats_payload, chart_payload, featured_records
from app.services.downloads import build_download_page_context, list_downloads
from app.services.bigscape import bigscape_summary
from app.services.bigscape_networks import default_gcf_accession
from app.database import db_connect, table_exists
from app.services.entities import (
    get_bgc_detail,
    get_gcf_detail,
    get_mag_detail,
    get_one_protein,
    get_protein_by_structure,
    grouped_search,
    list_bgcs,
    list_gcfs,
    list_mags,
    list_structures,
    resolve_legacy_accession,
)
from app.templates_env import templates

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
    try:
        protein = get_one_protein(public_protein_id)
    except HTTPException:
        canonical = resolve_legacy_accession("proteins", public_protein_id)
        if canonical:
            return _redirect(request, f"/proteins/{canonical}")
        raise HTTPException(404, 'Protein not found')
    with db_connect() as conn:
        related=[]
        if table_exists(conn,'bgc_protein_summary'):
            related=[dict(r._mapping) for r in conn.execute(text('select public_protein_id, query, product, mean_plddt, pdb_structural_match_category from bgc_protein_summary where bgc_id=:b and public_protein_id != :p limit 8'), {"b":protein.get('bgc_id'),"p":public_protein_id})]
    return templates.TemplateResponse('detail/protein.html', {"request":request,"protein":protein,"related":related,"active":"proteins"})

@router.get('/downloads')
def downloads(request: Request):
    context = {
        **build_download_page_context(),
        "active": "downloads",
    }
    return templates.TemplateResponse(request, 'downloads.html', context)


@router.head('/downloads')
def downloads_head():
    return Response(status_code=200, media_type="text/html")

@router.get('/help')
def help_page(request: Request): return templates.TemplateResponse('help.html', {"request":request,"active":"help"})
@router.get('/about')
def about(request: Request): return templates.TemplateResponse('about.html', {"request":request,"active":"about"})
@router.get('/contact')
def contact(request: Request): return templates.TemplateResponse('contact.html', {"request":request,"active":"contact"})
@router.get('/bgcs')
def bgcs_page(request: Request, page:int=1, page_size:int=25, sort_by:str='public_bgc_id', sort_dir:str='asc', q:str|None=None, mag:str|None=None, gcf:str|None=None, bgc_class:str|None=None, assigned:str|None=None):
    data = list_bgcs(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir, q=q, mag=mag, gcf=gcf, bgc_class=bgc_class, assigned=assigned)
    ctx={"request":request,"data":data,"q":q or "", "active":"bgcs", "entity":"bgcs", "title":"Browse BGCs", "description":"antiSMASH-predicted BGC regions linked to MAGs, primary c0.3 GCFs, proteins, structures, AF3 QC, and Foldseek/PDB annotations.", "filters":{"mag":mag or "", "gcf":gcf or "", "bgc_class":bgc_class or "", "assigned":assigned or ""}}
    tmpl='partials/entity_table.html' if request.headers.get('hx-request') else 'browse/entity.html'
    return templates.TemplateResponse(tmpl, ctx)
@router.get('/mags')
def mags_page(request: Request, page:int=1, page_size:int=25, sort_by:str='public_mag_id', sort_dir:str='asc', q:str|None=None, dataset:str|None=None):
    data = list_mags(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir, q=q, dataset=dataset)
    ctx={"request":request,"data":data,"q":q or "", "active":"mags", "entity":"mags", "title":"Browse MAGs", "description":"MAG records summarize oral microbiome metagenome-assembled genomes and their BGC, protein, predicted-structure, AF3 QC, and Foldseek/PDB coverage.", "filters":{"dataset":dataset or ""}}
    tmpl='partials/entity_table.html' if request.headers.get('hx-request') else 'browse/entity.html'
    return templates.TemplateResponse(tmpl, ctx)
@router.get('/gcfs')
def gcfs_page(request: Request, page:int=1, page_size:int=25, sort_by:str='public_gcf_id', sort_dir:str='asc', q:str|None=None, bgc_class:str|None=None):
    data = list_gcfs(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir, q=q, bgc_class=bgc_class)
    ctx={"request":request,"data":data,"q":q or "", "active":"gcfs", "entity":"gcfs", "title":"Primary BiG-SCAPE GCF assignments at cutoff c0.3", "description":"These GCF records use the primary c0.3 BiG-SCAPE assignment. All-cutoff assignment tables remain available for download.", "filters":{"bgc_class":bgc_class or ""}}
    tmpl='partials/entity_table.html' if request.headers.get('hx-request') else 'browse/entity.html'
    return templates.TemplateResponse(tmpl, ctx)
@router.get('/structures')
def structures_page(request: Request, page:int=1, page_size:int=25, sort_by:str='public_protein_id', sort_dir:str='asc', q:str|None=None, length_bucket:str|None=None, af3_qc_available:str|None=None, foldseek_annotation_available:str|None=None):
    data = list_structures(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir, q=q, length_bucket=length_bucket, af3_qc_available=af3_qc_available, foldseek_annotation_available=foldseek_annotation_available)
    ctx={"request":request,"data":data,"q":q or "", "active":"structures", "entity":"structures", "title":"Browse Structures", "description":"Approved predicted-structure CIF files joined to public protein metadata. Missing AF3 QC or Foldseek values are shown as not available in this release.", "filters":{"length_bucket":length_bucket or "", "af3_qc_available":af3_qc_available or "", "foldseek_annotation_available":foldseek_annotation_available or ""}}
    tmpl='partials/entity_table.html' if request.headers.get('hx-request') else 'browse/entity.html'
    return templates.TemplateResponse(tmpl, ctx)
@router.get('/search')
def search_page(request: Request, q:str|None=None, page_size:int=10):
    results = None
    error = None
    if q:
        try:
            results = grouped_search(q, page_size)
        except HTTPException as exc:
            error = exc.detail
    return templates.TemplateResponse('search.html', {"request":request,"q":q or "", "results":results, "error":error, "active":"search"})
@router.get('/networks')
def networks_page(request: Request):
    return templates.TemplateResponse('networks.html', {"request":request,"active":"networks", "default_gcf": default_gcf_accession(), **bigscape_summary()})

@router.get('/mags/{public_mag_id:path}')
def mag_detail(request: Request, public_mag_id: str):
    try:
        detail = get_mag_detail(public_mag_id)
    except HTTPException as exc:
        canonical = resolve_legacy_accession("mags", public_mag_id)
        if exc.status_code == 404 and canonical:
            return _redirect(request, f"/mags/{canonical}")
        raise
    return templates.TemplateResponse('detail/mag.html', {"request":request, **detail, "active":"mags"})

@router.get('/bgcs/{public_bgc_id:path}')
def bgc_detail(request: Request, public_bgc_id: str):
    try:
        detail = get_bgc_detail(public_bgc_id)
    except HTTPException as exc:
        canonical = resolve_legacy_accession("bgcs", public_bgc_id)
        if exc.status_code == 404 and canonical:
            return _redirect(request, f"/bgcs/{canonical}")
        raise
    genes = _layout_genes(detail["genes"])
    return templates.TemplateResponse('detail/bgc.html', {"request":request, **detail, "genes":genes, "active":"bgcs"})

@router.get('/gcfs/{public_gcf_id:path}')
def gcf_detail(request: Request, public_gcf_id: str):
    try:
        detail = get_gcf_detail(public_gcf_id)
    except HTTPException as exc:
        canonical = resolve_legacy_accession("gcfs", public_gcf_id)
        if exc.status_code == 404 and canonical:
            return _redirect(request, f"/gcfs/{canonical}")
        raise
    return templates.TemplateResponse('detail/gcf.html', {"request":request, **detail, "active":"gcfs"})


@router.get('/structures/{public_structure_id:path}')
def structure_detail(request: Request, public_structure_id: str):
    try:
        protein = get_protein_by_structure(public_structure_id)
    except HTTPException as exc:
        canonical = resolve_legacy_accession("structures", public_structure_id)
        if exc.status_code == 404 and canonical:
            return _redirect(request, f"/structures/{canonical}")
        raise
    with db_connect() as conn:
        related=[]
        if table_exists(conn,'bgc_protein_summary'):
            related=[dict(r._mapping) for r in conn.execute(text('select public_protein_id, query, product, mean_plddt, pdb_structural_match_category from bgc_protein_summary where bgc_id=:b and public_protein_id != :p limit 8'), {"b":protein.get('bgc_id'),"p":protein.get("public_protein_id")})]
    return templates.TemplateResponse('detail/protein.html', {"request":request,"protein":protein,"related":related,"active":"structures"})


def _redirect(request: Request, path: str) -> RedirectResponse:
    query = request.url.query
    location = f"{path}?{query}" if query else path
    return RedirectResponse(location, status_code=308)


def _layout_genes(genes):
    if not genes:
        return []
    starts=[int(float(g["cds_start"])) for g in genes if g.get("cds_start")]
    ends=[int(float(g["cds_end"])) for g in genes if g.get("cds_end")]
    if not starts or not ends:
        return []
    lo, hi = min(starts), max(ends)
    span=max(1, hi-lo)
    colors={"biosynthetic":"#007c89","biosynthetic-additional":"#2b8a3e","transport":"#b56b1d","regulatory":"#6b5fb5"}
    laid=[]
    for g in genes:
        start=int(float(g["cds_start"])); end=int(float(g["cds_end"]))
        x=40 + ((min(start,end)-lo)/span)*900
        w=max(8, (abs(end-start)/span)*900)
        kind_parts = (g.get("gene_kind") or "").split()
        kind = kind_parts[0] if kind_parts else ""
        laid.append({**g, "x":x, "width":w, "strand":str(g.get("cds_strand") or "1"), "color":colors.get(kind, "#7b8794")})
    return laid
