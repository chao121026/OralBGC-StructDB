from __future__ import annotations

from math import ceil
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.database import db_connect
from app.queries import public_row
from app.services.public_resources import first_resource_by_type, resource_for_entity


LIST_CONFIG = {
    "mags": {
        "id_col": "public_mag_id",
        "default_sort": "public_mag_id",
        "sorts": {
            "mag_accession", "public_mag_id", "mag_id", "original_mag_id", "number_BGCs", "number_BGC_proteins",
            "number_BiGSCAPE_GCFs", "predicted_structures_available",
            "proteins_with_af3_qc", "proteins_with_foldseek_annotation",
        },
        "search": ["m.mag_accession", "m.public_mag_id", "m.mag_id", "m.original_mag_id"],
    },
    "bgcs": {
        "id_col": "public_bgc_id",
        "default_sort": "public_bgc_id",
        "sorts": {
            "bgc_accession", "public_bgc_id", "region_basename", "mag_accession", "public_mag_id", "contig_id",
            "region_number", "bigscape_class_primary", "primary_gcf_accession", "public_gcf_id",
            "number_BGC_proteins", "predicted_structures_available",
            "proteins_with_af3_qc", "proteins_with_foldseek_annotation",
        },
        "search": ["b.bgc_accession", "b.public_bgc_id", "b.bgc_id", "b.original_bgc_id", "b.region_basename", "b.genome_id", "b.original_mag_id", "b.contig_id", "b.region_number"],
    },
    "gcfs": {
        "id_col": "public_gcf_id",
        "default_sort": "public_gcf_id",
        "sorts": {
            "primary_gcf_accession", "public_gcf_id", "bigscape_gcf_id_full_primary", "bigscape_class_primary",
            "number_BGCs", "number_MAGs", "number_BGC_proteins",
            "predicted_structures_available", "proteins_with_af3_qc",
            "proteins_with_foldseek_annotation",
        },
        "search": ["g.primary_gcf_accession", "g.public_gcf_id", "g.bigscape_gcf_id_full_primary", "g.bigscape_class_primary"],
    },
    "structures": {
        "id_col": "public_structure_id",
        "default_sort": "public_structure_id",
        "sorts": {
            "structure_accession", "public_structure_id", "protein_accession", "public_protein_id", "product", "sequence_length", "length_bucket",
            "structure_available", "af3_qc_available", "foldseek_annotation_available",
            "mean_plddt", "af3_confidence_class", "compactness_class",
            "pdb_structural_match_category",
        },
        "search": ["p.structure_accession", "p.public_structure_id", "p.protein_accession", "p.public_protein_id", "p.query", "p.original_protein_id", "p.original_structure_filename", "p.product", "p.gene_name", "p.target", "p.contig_id", "p.region_number"],
    },
}


def _page(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), get_settings().max_page_size))
    return page, page_size


def _like_clause(columns: list[str], q: str | None, params: dict[str, Any]) -> str:
    if not q:
        return ""
    params["q"] = f"%{q}%"
    return "(" + " or ".join([f"coalesce({col}, '') like :q" for col in columns]) + ")"


def _range_clause(field: str, min_value: int | None, max_value: int | None, params: dict[str, Any]) -> list[str]:
    clauses = []
    if min_value is not None:
        params[f"{field}_min"] = min_value
        clauses.append(f"cast({field} as real) >= :{field}_min")
    if max_value is not None:
        params[f"{field}_max"] = max_value
        clauses.append(f"cast({field} as real) <= :{field}_max")
    return clauses


def _canonical(entity: str, row: dict[str, Any]) -> dict[str, Any]:
    id_col = LIST_CONFIG[entity]["id_col"]
    if row.get(id_col):
        row["canonical_url"] = f"/{entity}/{row[id_col]}" if entity != "structures" else f"/structures/{row[id_col]}"
    return public_row(row)


def _paginate(entity: str, select_sql: str, count_sql: str, params: dict[str, Any], page: int, page_size: int, sort_by: str, sort_dir: str):
    cfg = LIST_CONFIG[entity]
    page, page_size = _page(page, page_size)
    sort_by = sort_by if sort_by in cfg["sorts"] else cfg["default_sort"]
    sort_dir = "desc" if str(sort_dir).lower() == "desc" else "asc"
    offset = (page - 1) * page_size
    with db_connect() as conn:
        total = conn.execute(text(count_sql), params).scalar_one()
        rows = [
            _canonical(entity, dict(r._mapping))
            for r in conn.execute(
                text(f"{select_sql} order by {sort_by} {sort_dir} limit :limit offset :offset"),
                {**params, "limit": page_size, "offset": offset},
            )
        ]
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if total else 0,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }


def list_mags(page=1, page_size=25, sort_by="public_mag_id", sort_dir="asc", q=None, dataset=None, **ranges):
    params: dict[str, Any] = {}
    clauses = []
    q_clause = _like_clause(LIST_CONFIG["mags"]["search"], q, params)
    if q_clause:
        clauses.append(q_clause)
    if dataset:
        params["dataset"] = dataset
        clauses.append("m.dataset = :dataset")
    clauses += _range_clause("number_BGCs", ranges.get("number_bgcs_min"), ranges.get("number_bgcs_max"), params)
    clauses += _range_clause("number_BiGSCAPE_GCFs", ranges.get("number_gcfs_min"), ranges.get("number_gcfs_max"), params)
    clauses += _range_clause("number_BGC_proteins", ranges.get("number_proteins_min"), ranges.get("number_proteins_max"), params)
    where = " where " + " and ".join(clauses) if clauses else ""
    base = """
        from mag_summary m
        left join (
            select public_mag_id,
                   sum(case when structure_available='1' then 1 else 0 end) predicted_structures_available,
                   sum(case when af3_qc_available='1' then 1 else 0 end) proteins_with_af3_qc,
                   sum(case when foldseek_annotation_available='1' then 1 else 0 end) proteins_with_foldseek_annotation
            from bgc_protein_summary group by public_mag_id
        ) c using(public_mag_id)
    """
    select_sql = f"""select m.dataset, m.mag_accession, m.public_mag_id, m.original_mag_id, m.mag_id, m.number_BGCs, m.number_BGC_proteins,
        m.number_BiGSCAPE_GCFs, coalesce(c.predicted_structures_available,0) predicted_structures_available,
        coalesce(c.proteins_with_af3_qc,0) proteins_with_af3_qc,
        coalesce(c.proteins_with_foldseek_annotation,0) proteins_with_foldseek_annotation {base} {where}"""
    return _paginate("mags", select_sql, f"select count(*) {base} {where}", params, page, page_size, sort_by, sort_dir)


def list_bgcs(page=1, page_size=25, sort_by="public_bgc_id", sort_dir="asc", q=None, dataset=None, mag=None, gcf=None, bgc_class=None, assigned=None, **ranges):
    params: dict[str, Any] = {}
    clauses = []
    q_clause = _like_clause(LIST_CONFIG["bgcs"]["search"], q, params)
    if q_clause:
        clauses.append(q_clause)
    for key, value, expr in [
        ("dataset", dataset, "b.dataset = :dataset"),
        ("mag", mag, "b.public_mag_id = :mag"),
        ("gcf", gcf, "b.public_gcf_id = :gcf"),
        ("bgc_class", bgc_class, "b.bigscape_class_primary = :bgc_class"),
    ]:
        if value:
            params[key] = value
            clauses.append(expr)
    if assigned == "assigned":
        clauses.append("coalesce(b.public_gcf_id, '') != ''")
    elif assigned == "unassigned":
        clauses.append("coalesce(b.public_gcf_id, '') = ''")
    clauses += _range_clause("number_BGC_proteins", ranges.get("number_proteins_min"), ranges.get("number_proteins_max"), params)
    where = " where " + " and ".join(clauses) if clauses else ""
    base = """
        from bgc_summary b
        left join (
            select public_bgc_id,
                   sum(case when structure_available='1' then 1 else 0 end) predicted_structures_available,
                   sum(case when af3_qc_available='1' then 1 else 0 end) proteins_with_af3_qc,
                   sum(case when foldseek_annotation_available='1' then 1 else 0 end) proteins_with_foldseek_annotation
            from bgc_protein_summary group by public_bgc_id
        ) c using(public_bgc_id)
    """
    select_sql = f"""select b.dataset, b.bgc_accession, b.public_bgc_id, b.original_bgc_id, b.bgc_id, b.region_basename, b.mag_accession, b.public_mag_id,
        b.original_mag_id, b.genome_id, b.contig_id, b.region_number, b.bigscape_class_primary, b.primary_gcf_accession, b.public_gcf_id,
        b.bigscape_gcf_id_full_primary, b.number_BGC_proteins,
        coalesce(c.predicted_structures_available,0) predicted_structures_available,
        coalesce(c.proteins_with_af3_qc,0) proteins_with_af3_qc,
        coalesce(c.proteins_with_foldseek_annotation,0) proteins_with_foldseek_annotation {base} {where}"""
    return _paginate("bgcs", select_sql, f"select count(*) {base} {where}", params, page, page_size, sort_by, sort_dir)


def list_gcfs(page=1, page_size=25, sort_by="public_gcf_id", sort_dir="asc", q=None, dataset=None, bgc_class=None, **ranges):
    params: dict[str, Any] = {}
    clauses = []
    q_clause = _like_clause(LIST_CONFIG["gcfs"]["search"], q, params)
    if q_clause:
        clauses.append(q_clause)
    if dataset:
        params["dataset"] = dataset
        clauses.append("g.dataset = :dataset")
    if bgc_class:
        params["bgc_class"] = bgc_class
        clauses.append("g.bigscape_class_primary = :bgc_class")
    clauses += _range_clause("number_BGCs", ranges.get("number_bgcs_min"), ranges.get("number_bgcs_max"), params)
    clauses += _range_clause("number_MAGs", ranges.get("number_mags_min"), ranges.get("number_mags_max"), params)
    where = " where " + " and ".join(clauses) if clauses else ""
    base = """
        from bigscape_gcf_summary g
        left join (
            select public_gcf_id,
                   sum(case when structure_available='1' then 1 else 0 end) predicted_structures_available,
                   sum(case when af3_qc_available='1' then 1 else 0 end) proteins_with_af3_qc,
                   sum(case when foldseek_annotation_available='1' then 1 else 0 end) proteins_with_foldseek_annotation
            from bgc_protein_summary where coalesce(public_gcf_id,'') != '' group by public_gcf_id
        ) c using(public_gcf_id)
    """
    select_sql = f"""select g.dataset, g.gcf_accession, g.primary_gcf_accession, g.public_gcf_id, g.bigscape_gcf_id_full_primary,
        g.bigscape_class_primary, g.number_BGCs, g.number_MAGs, g.number_BGC_proteins,
        coalesce(c.predicted_structures_available,0) predicted_structures_available,
        coalesce(c.proteins_with_af3_qc,0) proteins_with_af3_qc,
        coalesce(c.proteins_with_foldseek_annotation,0) proteins_with_foldseek_annotation {base} {where}"""
    return _paginate("gcfs", select_sql, f"select count(*) {base} {where}", params, page, page_size, sort_by, sort_dir)


def list_structures(page=1, page_size=25, sort_by="public_protein_id", sort_dir="asc", q=None, **filters):
    params: dict[str, Any] = {}
    clauses = ["p.structure_available = '1'"]
    q_clause = _like_clause(LIST_CONFIG["structures"]["search"], q, params)
    if q_clause:
        clauses.append(q_clause)
    for col in ["dataset", "length_bucket", "structure_available", "af3_qc_available", "foldseek_annotation_available", "af3_confidence_class", "compactness_class", "pdb_structural_match_category"]:
        if filters.get(col):
            params[col] = filters[col]
            clauses.append(f"p.{col} = :{col}")
    if filters.get("weak_only"):
        clauses.append("coalesce(p.pdb_structural_match_category,'') in ('weak_or_no_clear_PDB_match','no_clear_PDB_match','weak_PDB_match','')")
    clauses += _range_clause("sequence_length", filters.get("sequence_length_min"), filters.get("sequence_length_max"), params)
    clauses += _range_clause("mean_plddt", filters.get("mean_plddt_min"), filters.get("mean_plddt_max"), params)
    where = " where " + " and ".join(clauses)
    base = "from bgc_protein_summary p"
    select_sql = f"""select p.dataset, p.protein_accession, p.public_protein_id, p.original_protein_id, p.structure_accession, p.public_structure_id, p.original_structure_filename, p.query, p.product, p.sequence_length,
        p.length_bucket, p.structure_available, p.af3_qc_available, p.foldseek_annotation_available,
        p.mean_plddt, p.af3_confidence_class, p.compactness_class, p.pdb_structural_match_category {base} {where}"""
    return _paginate("structures", select_sql, f"select count(*) {base} {where}", params, page, page_size, sort_by, sort_dir)


def search_proteins(page_size=10, q=None):
    params: dict[str, Any] = {}
    clauses = []
    q_clause = _like_clause(LIST_CONFIG["structures"]["search"], q, params)
    if q_clause:
        clauses.append(q_clause)
    where = " where " + " and ".join(clauses) if clauses else ""
    select_sql = """select p.dataset, p.protein_accession, p.public_protein_id, p.original_protein_id, p.structure_accession, p.public_structure_id, p.query, p.product, p.gene_name,
        p.target, p.region_basename, p.sequence_length, p.length_bucket, p.structure_available,
        p.af3_qc_available, p.foldseek_annotation_available
        from bgc_protein_summary p""" + where
    return _paginate("structures", select_sql, "select count(*) from bgc_protein_summary p" + where, params, 1, page_size, "public_protein_id", "asc")


def get_entity(entity: str, public_id: str):
    id_col = LIST_CONFIG[entity]["id_col"]
    data = {"mags": list_mags, "bgcs": list_bgcs, "gcfs": list_gcfs}[entity](page=1, page_size=1, q=None)
    # Avoid relying on list search for IDs that contain separators.
    tables = {"mags": "mag_summary", "bgcs": "bgc_summary", "gcfs": "bigscape_gcf_summary"}
    with db_connect() as conn:
        row = conn.execute(text(f"select * from {tables[entity]} where {id_col}=:id limit 1"), {"id": public_id}).first()
    if not row:
        raise HTTPException(404, f"{entity[:-1].upper()} not found")
    # Return enriched row by filtering the list on exact ID.
    enriched = {"mags": list_mags, "bgcs": list_bgcs, "gcfs": list_gcfs}[entity](page=1, page_size=1, q=None, sort_by=id_col)
    for item in [dict(row._mapping)]:
        return public_row(item)
    return data["items"][0]


def resolve_legacy_accession(entity: str, identifier: str) -> str | None:
    candidates = [identifier]
    if identifier.startswith("PHRC|"):
        candidates.append(identifier.removeprefix("PHRC|"))
    tables = {
        "mags": ("mag_summary", "public_mag_id", ["mag_id", "original_mag_id"]),
        "bgcs": ("bgc_summary", "public_bgc_id", ["bgc_id", "original_bgc_id", "region_basename"]),
        "gcfs": ("bigscape_gcf_summary", "public_gcf_id", ["bigscape_gcf_id_full_primary"]),
        "proteins": ("bgc_protein_summary", "public_protein_id", ["query", "original_protein_id"]),
        "structures": ("bgc_protein_summary", "public_structure_id", ["query", "original_protein_id", "original_structure_filename"]),
    }
    table, public_col, legacy_cols = tables[entity]
    clauses = " or ".join([f"{col}=:identifier" for col in legacy_cols])
    with db_connect() as conn:
        row = None
        for candidate in candidates:
            row = conn.execute(text(f"select {public_col} from {table} where {clauses} limit 1"), {"identifier": candidate}).first()
            if row:
                break
    return row._mapping[public_col] if row else None


def get_protein_by_structure(public_structure_id: str):
    with db_connect() as conn:
        row = conn.execute(text("select public_protein_id from bgc_protein_summary where public_structure_id=:id limit 1"), {"id": public_structure_id}).first()
    if not row:
        raise HTTPException(404, "Structure not found")
    return get_one_protein(row._mapping["public_protein_id"])


def get_one_protein(public_protein_id: str):
    with db_connect() as conn:
        row = conn.execute(text("select * from bgc_protein_summary where public_protein_id=:id limit 1"), {"id": public_protein_id}).first()
    if not row:
        raise HTTPException(404, "Protein not found")
    protein = public_row(dict(row._mapping))
    if protein.get("public_structure_id"):
        protein["structure_resource"] = resource_for_entity("structures", protein["public_structure_id"])
    protein["protein_fasta_resource"] = first_resource_by_type("protein_fasta")
    return protein


def get_mag_detail(public_mag_id: str):
    summary = list_mags(page=1, page_size=1, q=public_mag_id)["items"]
    mag = next((m for m in summary if m["public_mag_id"] == public_mag_id), None)
    if not mag:
        with db_connect() as conn:
            row = conn.execute(text("select * from mag_summary where public_mag_id=:id"), {"id": public_mag_id}).first()
        if not row:
            raise HTTPException(404, "MAG not found")
        mag = public_row(dict(row._mapping))
    with db_connect() as conn:
        bgcs = [public_row(dict(r._mapping)) for r in conn.execute(text("select public_bgc_id, region_basename, bigscape_class_primary, public_gcf_id, number_BGC_proteins from bgc_summary where public_mag_id=:id order by public_bgc_id limit 25"), {"id": public_mag_id})]
        proteins = [public_row(dict(r._mapping)) for r in conn.execute(text("select public_protein_id, product, length_bucket, structure_available, af3_qc_available, foldseek_annotation_available from bgc_protein_summary where public_mag_id=:id order by public_protein_id limit 25"), {"id": public_mag_id})]
        gcfs = [public_row(dict(r._mapping)) for r in conn.execute(text("select distinct public_gcf_id, bigscape_gcf_id_full_primary, bigscape_class_primary from bgc_summary where public_mag_id=:id and coalesce(public_gcf_id,'')!='' order by public_gcf_id limit 25"), {"id": public_mag_id})]
        class_dist = [dict(r._mapping) for r in conn.execute(text("select coalesce(bigscape_class_primary,'Unassigned') label, count(*) value from bgc_summary where public_mag_id=:id group by coalesce(bigscape_class_primary,'Unassigned')"), {"id": public_mag_id})]
        length_dist = [dict(r._mapping) for r in conn.execute(text("select length_bucket label, count(*) value from bgc_protein_summary where public_mag_id=:id group by length_bucket"), {"id": public_mag_id})]
    return {
        "record": mag,
        "bgcs": bgcs,
        "proteins": proteins,
        "gcfs": gcfs,
        "class_dist": class_dist,
        "length_dist": length_dist,
        "mag_resource": resource_for_entity("mags", public_mag_id),
    }


def get_bgc_detail(public_bgc_id: str):
    with db_connect() as conn:
        row = conn.execute(text("select * from bgc_summary where public_bgc_id=:id"), {"id": public_bgc_id}).first()
        if not row:
            raise HTTPException(404, "BGC not found")
        record = public_row(dict(row._mapping))
        proteins = [public_row(dict(r._mapping)) for r in conn.execute(text("select public_protein_id, query, product, gene_kind, locus_tag, length_bucket, structure_available, af3_qc_available, foldseek_annotation_available from bgc_protein_summary where public_bgc_id=:id order by cast(cds_index_in_region as integer) limit 200"), {"id": public_bgc_id})]
        genes = [public_row(dict(r._mapping)) for r in conn.execute(text("select public_protein_id, query, locus_tag, product, gene_kind, cds_start, cds_end, cds_strand from integrated_summary where public_bgc_id=:id and coalesce(cds_start,'')!='' and coalesce(cds_end,'')!='' order by cast(cds_start as integer) limit 300"), {"id": public_bgc_id})]
        coverage = conn.execute(text("select sum(case when structure_available='1' then 1 else 0 end) structures, sum(case when af3_qc_available='1' then 1 else 0 end) af3_qc, sum(case when foldseek_annotation_available='1' then 1 else 0 end) foldseek from bgc_protein_summary where public_bgc_id=:id"), {"id": public_bgc_id}).first()
    return {
        "record": record,
        "proteins": proteins,
        "genes": genes,
        "coverage": dict(coverage._mapping) if coverage else {},
        "bgc_archive_resource": first_resource_by_type("bgc_bulk_archive"),
    }


def get_gcf_detail(public_gcf_id: str):
    with db_connect() as conn:
        row = conn.execute(text("select * from bigscape_gcf_summary where public_gcf_id=:id"), {"id": public_gcf_id}).first()
        if not row:
            raise HTTPException(404, "GCF not found")
        record = public_row(dict(row._mapping))
        bgcs = [public_row(dict(r._mapping)) for r in conn.execute(text("select public_bgc_id, region_basename, public_mag_id, bigscape_class_primary, number_BGC_proteins from bgc_summary where public_gcf_id=:id order by public_bgc_id limit 50"), {"id": public_gcf_id})]
        mags = [public_row(dict(r._mapping)) for r in conn.execute(text("select distinct public_mag_id, genome_id from bgc_summary where public_gcf_id=:id order by public_mag_id limit 50"), {"id": public_gcf_id})]
        proteins = [public_row(dict(r._mapping)) for r in conn.execute(text("select public_protein_id, product, length_bucket, structure_available, af3_qc_available, foldseek_annotation_available from bgc_protein_summary where public_gcf_id=:id order by public_protein_id limit 50"), {"id": public_gcf_id})]
        coverage = conn.execute(text("select count(*) proteins, sum(case when structure_available='1' then 1 else 0 end) structures, sum(case when af3_qc_available='1' then 1 else 0 end) af3_qc, sum(case when foldseek_annotation_available='1' then 1 else 0 end) foldseek from bgc_protein_summary where public_gcf_id=:id"), {"id": public_gcf_id}).first()
    return {"record": record, "bgcs": bgcs, "mags": mags, "proteins": proteins, "coverage": dict(coverage._mapping) if coverage else {}}


def grouped_search(q: str, page_size: int = 10):
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "Search query must contain at least two characters")
    q = q.strip()
    return {
        "q": q,
        "groups": {
            "mags": list_mags(page=1, page_size=page_size, q=q),
            "bgcs": list_bgcs(page=1, page_size=page_size, q=q),
            "gcfs": list_gcfs(page=1, page_size=page_size, q=q),
            "proteins": search_proteins(page_size=page_size, q=q),
        },
    }
