from pathlib import Path
from sqlalchemy import text
from fastapi import HTTPException
from app.config import get_settings
from app.database import db_connect, table_exists
from app.security import reject_unsafe_identifier, safe_under

RECOMMENDED = "recommended"
ADVANCED = "advanced"
DOCUMENTATION = "documentation"

PRESENTATION = {
    "b862769ad9efb444": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 1,
        "is_primary": True,
        "record_count": 22626,
        "recommended_label": "Recommended primary metadata table",
        "display_description": "Integrated public BGC, protein, AF3 structure, QC, and Foldseek/PDB metadata.",
        "usage_note": "Best for: most downstream analyses",
        "badges": ["Recommended", "Primary table"],
    },
    "7ba87e486134d8cc": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 2,
        "record_count": 22626,
        "usage_note": "Best for: sequence-based analysis",
        "badges": ["Recommended", "Sequences"],
    },
    "ac563352d57b2488": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 3,
        "record_count": 179,
        "display_description": "Primary c0.3 BiG-SCAPE GCF summary table.",
        "usage_note": "Best for: primary GCF assignments",
        "badges": ["Recommended", "GCF assignments"],
    },
    "e9f852398ed32baf": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 4,
        "record_count": 1913,
        "usage_note": "Best for: BGC annotation review",
        "badges": ["Recommended", "BGC annotations"],
    },
    "64fb7d7a896d909b": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 5,
        "usage_note": "Best for: short protein structure analysis",
        "badges": ["Recommended", "Structures"],
    },
    "d50f02218a6d055c": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 6,
        "usage_note": "Best for: medium protein structure analysis",
        "badges": ["Recommended", "Structures"],
    },
    "20bd4da3b8143738": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 7,
        "usage_note": "Best for: long protein structure analysis",
        "badges": ["Recommended", "Structures"],
    },
    "9f7cbce127b94a94": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 8,
        "usage_note": "Best for: release orientation",
        "badges": ["Recommended", "Documentation"],
    },
    "3c4841d919385ac3": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 9,
        "usage_note": "Best for: interpreting public table columns",
        "badges": ["Recommended", "Documentation"],
    },
    "da72bfb7f01ce319": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 10,
        "usage_note": "Best for: checksum verification",
        "badges": ["Recommended", "Documentation"],
    },
    "dbfde162c9d0ba3d": {"advanced_group": "Component tables", "record_count": 583},
    "863fab4f6f02aafd": {"advanced_group": "Component tables", "record_count": 1913},
    "ebf946aa24661cac": {"advanced_group": "Component tables", "record_count": 22626},
    "6769793bb4d3c6aa": {"advanced_group": "Component tables", "record_count": 10972},
    "a16602cce130c1b1": {"advanced_group": "BiG-SCAPE", "record_count": 8731},
    "ba758418d85f2eda": {"advanced_group": "Foldseek", "record_count": 10972},
    "c146a7ba908080a2": {"advanced_group": "Foldseek", "record_count": 10972},
    "b854f6dca2c1ad4d": {"advanced_group": "Foldseek", "record_count": 10972},
    "7fbf2ee4000ce551": {"advanced_group": "Foldseek", "record_count": 10972},
    "1e60bd010691d9e1": {"advanced_group": "Foldseek"},
    "ec593e14f67956a4": {"advanced_group": "BiG-SCAPE"},
    "1b9a1509a78805ef": {"advanced_group": "BiG-SCAPE"},
    "b44b5de0e2b61216": {
        "advanced_group": "BiG-SCAPE",
        "is_empty": True,
        "availability": "unavailable",
        "usage_note": "Unavailable in this release: the packaged Cytoscape archive is empty.",
    },
    "12dddbaafd0d8e43": {"advanced_group": "antiSMASH"},
    "31c35d3532a24653": {"advanced_group": "Documentation"},
    "5927fd166dfe36f8": {"advanced_group": "Documentation"},
    "5d92acb254a3a7ca": {
        "advanced_group": "Documentation",
        "visible": False,
        "usage_note": "Duplicate public column dictionary entry retained in the allowlist.",
    },
}

ACCESSION_PRESENTATION = {
    "PHRC_integrated_BGC_protein_structure_summary.tsv": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 1,
        "is_primary": True,
        "record_count": 22626,
        "recommended_label": "Recommended primary metadata table",
        "display_description": "Accession-based integrated BGC, protein, predicted structure, AF3 QC, and Foldseek/PDB metadata.",
        "usage_note": "Best for: most downstream analyses with stable BGS accessions",
        "badges": ["Recommended", "Primary table"],
    },
    "BGS_public_accession_mapping.tsv": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 2,
        "record_count": 47923,
        "display_description": "Public BGS accession mapping with original PHRC identifiers retained as provenance.",
        "usage_note": "Best for: mapping original PHRC identifiers to stable BGS accessions",
        "badges": ["Recommended", "Accession mapping"],
    },
    "BGS_BGC_proteins_v1.0.faa": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 3,
        "record_count": 22626,
        "usage_note": "Best for: sequence-based analysis",
        "badges": ["Recommended", "Sequences"],
    },
    "BiGSCAPE_GCF_summary.tsv": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 4,
        "record_count": 179,
        "display_description": "BGS primary c0.3 BiG-SCAPE GCF summary table.",
        "usage_note": "Best for: primary GCF assignments",
        "badges": ["Recommended", "GCF assignments"],
    },
    "BiGSCAPE_BGC_to_GCF.tsv": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 5,
        "record_count": 8731,
        "usage_note": "Best for: all-cutoff GCF assignment reproducibility",
        "badges": ["Recommended", "GCF assignments"],
    },
    "BGS_BGC_GBK_v1.0.tar.gz": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 6,
        "record_count": 1913,
        "usage_note": "Best for: accession-named BGC GenBank records",
        "badges": ["Recommended", "BGC annotations"],
    },
    "BGS_structures_short_v1.0.tar.gz": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 7,
        "usage_note": "Best for: short protein structure analysis",
        "badges": ["Recommended", "Structures"],
    },
    "BGS_structures_medium_v1.0.tar.gz": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 8,
        "usage_note": "Best for: medium protein structure analysis",
        "badges": ["Recommended", "Structures"],
    },
    "BGS_structures_long_v1.0.tar.gz": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 9,
        "usage_note": "Best for: long protein structure analysis",
        "badges": ["Recommended", "Structures"],
    },
    "sha256sums.txt": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 10,
        "usage_note": "Best for: checksum verification",
        "badges": ["Recommended", "Checksums"],
    },
    "md5sums.txt": {
        "audience_level": RECOMMENDED,
        "recommended_rank": 11,
        "usage_note": "Best for: compatibility checksum verification",
        "badges": ["Recommended", "Checksums"],
    },
}

ADVANCED_GROUP_ORDER = {
    "Component tables": 1,
    "Foldseek": 2,
    "BiG-SCAPE": 3,
    "antiSMASH": 4,
    "Raw outputs": 5,
    "Documentation": 6,
}


def list_downloads():
    with db_connect() as conn:
        if not table_exists(conn, 'download_manifest'):
            return []
        has_sha = conn.execute(text("select 1 from pragma_table_info('download_manifest') where name='sha256'")).first()
        sha_expr = "sha256" if has_sha else "'' as sha256"
        rows = [dict(r._mapping) for r in conn.execute(text(f"select file_key, filename, description, category, size_bytes, compression, md5, {sha_expr}, version, modified_date from download_manifest where public_safe=1 order by category, filename"))]
    return sorted((_with_presentation(row) for row in rows), key=_download_sort_key)


def build_download_page_context() -> dict:
    items = list_downloads()
    recommended = [item for item in items if item["audience_level"] == RECOMMENDED and item["visible"]]
    advanced = [item for item in items if item["audience_level"] == ADVANCED and item["visible"]]
    advanced_groups = {}
    for item in advanced:
        advanced_groups.setdefault(item["advanced_group"], []).append(item)
    advanced_groups = dict(sorted(advanced_groups.items(), key=lambda pair: ADVANCED_GROUP_ORDER.get(pair[0], 99)))
    return {
        "recommended_downloads": recommended,
        "advanced": advanced,
        "advanced_groups": advanced_groups,
        "advanced_count": len(advanced),
        "download_count": len([item for item in items if item["visible"]]),
    }


def download_sections():
    context = build_download_page_context()
    return {
        **context,
        "recommended": context["recommended_downloads"],
    }


def _with_presentation(row):
    meta = ACCESSION_PRESENTATION.get(row["filename"]) or PRESENTATION.get(row["file_key"], {})
    level = meta.get("audience_level", ADVANCED)
    is_empty = bool(meta.get("is_empty", row.get("size_bytes") in {0, 45}))
    availability = meta.get("availability", "unavailable" if is_empty else "available")
    item = {
        **row,
        "audience_level": level,
        "recommended_rank": meta.get("recommended_rank"),
        "is_primary": bool(meta.get("is_primary", False)),
        "is_empty": is_empty,
        "record_count": meta.get("record_count"),
        "usage_note": meta.get("usage_note", _default_usage_note(row, level)),
        "recommended_label": meta.get("recommended_label"),
        "display_description": meta.get("display_description", row.get("description") or ""),
        "badges": meta.get("badges", _default_badges(row, level)),
        "advanced_group": meta.get("advanced_group", _default_advanced_group(row)),
        "availability": availability,
        "visible": meta.get("visible", True),
    }
    item["download_url"] = None if availability != "available" else f"/downloads/file/{row['file_key']}"
    return item


def _download_sort_key(item):
    if item["audience_level"] == RECOMMENDED:
        return (0, item["recommended_rank"] or 999, item["filename"])
    return (
        1,
        ADVANCED_GROUP_ORDER.get(item["advanced_group"], 99),
        item["filename"].lower(),
    )


def _default_badges(row, level):
    if level == RECOMMENDED:
        return ["Recommended", row["category"]]
    return [row["category"]]


def _default_usage_note(row, level):
    if level == RECOMMENDED:
        return "Best for: public release analysis"
    return "For reproducibility or specialist workflows"


def _default_advanced_group(row):
    category = row.get("category") or "Raw outputs"
    if category == "Tables":
        return "Component tables"
    if category in {"Foldseek", "BiG-SCAPE", "antiSMASH", "Documentation"}:
        return category
    return "Raw outputs"

def resolve_download(file_key: str) -> tuple[Path, str]:
    reject_unsafe_identifier(file_key)
    with db_connect() as conn:
        if not table_exists(conn, 'download_manifest'): raise HTTPException(404, 'No download manifest')
        row=conn.execute(text("select relative_path, filename from download_manifest where file_key=:k and public_safe=1"), {"k": file_key}).first()
    if not row: raise HTTPException(404, 'Download not found')
    root=get_settings().resolve_package_root()
    path=safe_under(root / row._mapping['relative_path'], root)
    if not path.exists() or not path.is_file(): raise HTTPException(404, 'File missing')
    return path, row._mapping['filename']
