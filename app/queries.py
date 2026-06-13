from math import ceil
from sqlalchemy import text
from .config import get_settings
from .database import db_connect, table_exists

HIDDEN_RESPONSE_COLUMNS = {
    'region_file', 'model_cif', 'bigscape_source_file', 'region_file_ranking'
}

def public_row(row):
    return {k: v for k, v in row.items() if k not in HIDDEN_RESPONSE_COLUMNS and not k.endswith('_file') and not k.endswith('_path')}

ALLOWED_SORTS = {
    "bgc_protein_summary": {"public_protein_id","query","region_basename","public_bgc_id","public_gcf_id","public_mag_id","product","gene_kind","sequence_length","length_bucket","mean_plddt","compactness_class","target","prob","alntmscore","pdb_structural_match_category","structure_available","af3_qc_available","foldseek_annotation_available"},
    "download_manifest": {"filename","category","size_bytes","modified_date"},
}
SEARCH_COLUMNS = {
    "bgc_protein_summary": ["public_protein_id","query","region_basename","bgc_id","bigscape_gcf_id_full_primary","genome_id","product","gene_name","target"],
}

def clamp_page(page:int, page_size:int):
    page=max(1, int(page or 1)); size=max(1, min(int(page_size or 25), get_settings().max_page_size)); return page,size

def paged_table(table, page=1, page_size=25, sort_by=None, sort_dir='asc', q=None, filters=None):
    filters=filters or {}; page,page_size=clamp_page(page,page_size)
    sort_by = sort_by if sort_by in ALLOWED_SORTS.get(table,set()) else next(iter(ALLOWED_SORTS.get(table,{"rowid"})))
    sort_dir = 'desc' if str(sort_dir).lower() == 'desc' else 'asc'
    clauses=[]; params={}
    if q and table in SEARCH_COLUMNS:
        parts=[]
        for i,col in enumerate(SEARCH_COLUMNS[table]):
            parts.append(f"coalesce({col}, '') like :q")
        clauses.append('(' + ' or '.join(parts) + ')'); params['q']=f"%{q}%"
    for col,val in filters.items():
        if val not in (None,'') and col in ALLOWED_SORTS.get(table,set()).union({'dataset','af3_confidence_class','structure_available','af3_qc_available','foldseek_annotation_available'}):
            clauses.append(f"{col} = :f_{col}"); params[f'f_{col}']=val
    where = ' where ' + ' and '.join(clauses) if clauses else ''
    offset=(page-1)*page_size
    with db_connect() as conn:
        if not table_exists(conn, table):
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
        total=conn.execute(text(f"select count(*) from {table}{where}"), params).scalar_one()
        sql=f"select * from {table}{where} order by {sort_by} {sort_dir} limit :limit offset :offset"
        rows=[public_row(dict(r._mapping)) for r in conn.execute(text(sql), {**params,'limit':page_size,'offset':offset})]
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "total_pages": ceil(total/page_size) if total else 0, "sort_by": sort_by, "sort_dir": sort_dir}

def get_one_by_public_id(table, id_col, public_id):
    with db_connect() as conn:
        if not table_exists(conn, table): return None
        row=conn.execute(text(f"select * from {table} where {id_col}=:id limit 1"), {"id": public_id}).first()
        return public_row(dict(row._mapping)) if row else None
