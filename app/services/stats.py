from sqlalchemy import text
from app.database import db_connect, table_exists

def stats_payload():
    with db_connect() as conn:
        def count(table, col=None, where=''):
            if not table_exists(conn, table): return 0
            expr=f"count(distinct {col})" if col else "count(*)"
            return conn.execute(text(f"select {expr} from {table} {where}")).scalar_one()
        return {
            "mags": count('mag_summary','public_mag_id'),
            "bgcs": count('bgc_summary','public_bgc_id'),
            "gcfs": count('bigscape_gcf_summary','public_gcf_id'),
            "proteins": count('bgc_protein_summary','public_protein_id'),
            "af3_models": count('af3_model_summary','public_protein_id'),
            "foldseek_annotations": count('foldseek_besthit_all','public_protein_id'),
        }

def chart_payload():
    with db_connect() as conn:
        if not table_exists(conn, 'bgc_protein_summary'):
            return {}
        def grouped(col):
            return [dict(r._mapping) for r in conn.execute(text(f"select coalesce({col}, 'Unassigned') as label, count(*) as value from bgc_protein_summary group by coalesce({col}, 'Unassigned') order by value desc limit 12"))]
        return {
            'bgc_class': grouped('bigscape_class_primary'),
            'confidence': grouped('af3_confidence_class'),
            'compactness': grouped('compactness_class'),
            'pdb_category': grouped('pdb_structural_match_category'),
        }

def featured_records():
    with db_connect() as conn:
        out={}
        for key, table, order in [('protein','bgc_protein_summary','mean_plddt desc'),('bgc','bgc_summary','number_AF3_models desc'),('mag','mag_summary','number_AF3_models desc'),('gcf','bigscape_gcf_summary','number_BGC_proteins desc')]:
            if table_exists(conn, table):
                row=conn.execute(text(f"select * from {table} order by {order} limit 1")).first()
                out[key]=dict(row._mapping) if row else None
        return out
