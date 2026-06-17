from sqlalchemy import text

from app.database import db_connect
from app.services.downloads import list_downloads


BIGSCAPE_DOWNLOADS = {
    "bgc_to_gcf_c0.3.tsv",
    "gcf_summary_c0.3.tsv",
    "bigscape_class_summary_c0.3.tsv",
    "bigscape_public_tables.tar.gz",
    "bigscape_primary_c0.3_networks.tar.gz",
    "bigscape_alternative_cutoff_networks.tar.gz",
    "network_file_manifest.tsv",
    "manifest.tsv",
    "SHA256SUMS",
}


def bigscape_summary() -> dict:
    with db_connect() as conn:
        totals = conn.execute(text("""
            select
              (select count(*) from bgc_summary) as bgc_count,
              (select count(*) from mag_summary) as mag_count,
              (select count(*) from bgc_protein_summary) as protein_count,
              (select count(*) from bgc_protein_summary where structure_available='1') as structure_count,
              (select count(distinct public_gcf_id) from bigscape_gcf_summary) as primary_gcf_count,
              (select count(distinct public_bgc_id) from bgc_summary where coalesce(public_gcf_id,'') != '') as assigned_bgc_count,
              (select count(distinct public_mag_id) from bgc_summary where coalesce(public_gcf_id,'') != '') as assigned_mag_count,
              (select count(distinct bigscape_class_primary) from bigscape_gcf_summary where coalesce(bigscape_class_primary,'') != '') as class_count,
              (select max(cast(number_BGCs as integer)) from bigscape_gcf_summary) as largest_gcf_size,
              (select count(*) from bigscape_gcf_summary where cast(number_BGCs as integer)=1) as singleton_gcf_count
        """)).mappings().one()
        classes = [dict(row._mapping) for row in conn.execute(text("""
            select g.bigscape_class_primary as bigscape_class,
                   count(*) as gcf_count,
                   sum(cast(g.number_BGCs as integer)) as bgc_count
            from bigscape_gcf_summary g
            group by g.bigscape_class_primary
            order by bgc_count desc, bigscape_class
        """))]
        top_gcfs = [dict(row._mapping) for row in conn.execute(text("""
            select g.public_gcf_id, g.primary_gcf_accession, g.bigscape_gcf_id_full_primary,
                   g.bigscape_class_primary, g.number_BGCs, g.number_MAGs, g.number_BGC_proteins,
                   coalesce(c.predicted_structures_available, 0) as predicted_structures_available
            from bigscape_gcf_summary g
            left join (
              select public_gcf_id, sum(case when structure_available='1' then 1 else 0 end) as predicted_structures_available
              from bgc_protein_summary
              where coalesce(public_gcf_id,'') != ''
              group by public_gcf_id
            ) c using(public_gcf_id)
            order by cast(g.number_BGCs as integer) desc, g.public_gcf_id
            limit 10
        """))]
    downloads = [item for item in list_downloads() if item["filename"] in BIGSCAPE_DOWNLOADS and item["availability"] == "available"]
    return {
        "primary_cutoff": "0.3",
        **dict(totals),
        "classes": classes,
        "top_gcfs": top_gcfs,
        "downloads": downloads,
    }
