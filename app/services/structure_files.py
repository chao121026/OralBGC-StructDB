from pathlib import Path
from sqlalchemy import text
from fastapi import HTTPException
from app.config import get_settings
from app.database import db_connect, table_exists
from app.security import reject_unsafe_identifier, safe_under

def resolve_cif(public_protein_id: str) -> tuple[Path, str]:
    reject_unsafe_identifier(public_protein_id.replace('|',''))
    with db_connect() as conn:
        if not table_exists(conn, 'structure_file_map'): raise HTTPException(404, 'No structure map')
        row=conn.execute(text("select relative_path, filename from structure_file_map where public_protein_id=:id and public_safe=1"), {"id": public_protein_id}).first()
    if not row: raise HTTPException(404, 'Structure not found')
    root=get_settings().resolve_package_root()
    path=safe_under(root / row._mapping['relative_path'], root / 'structures')
    if path.suffix != '.cif': raise HTTPException(403, 'Only CIF files are served')
    if not path.exists(): raise HTTPException(404, 'CIF file missing')
    return path, row._mapping['filename']
