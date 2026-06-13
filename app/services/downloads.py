from pathlib import Path
from sqlalchemy import text
from fastapi import HTTPException
from app.config import get_settings
from app.database import db_connect, table_exists
from app.security import reject_unsafe_identifier, safe_under

def list_downloads():
    with db_connect() as conn:
        if not table_exists(conn, 'download_manifest'):
            return []
        return [dict(r._mapping) for r in conn.execute(text("select file_key, filename, description, category, size_bytes, compression, md5, version, modified_date from download_manifest order by category, filename"))]

def resolve_download(file_key: str) -> tuple[Path, str]:
    reject_unsafe_identifier(file_key)
    with db_connect() as conn:
        if not table_exists(conn, 'download_manifest'): raise HTTPException(404, 'No download manifest')
        row=conn.execute(text("select relative_path, filename from download_manifest where file_key=:k and public_safe=1"), {"k": file_key}).first()
    if not row: raise HTTPException(404, 'Download not found')
    root=get_settings().package_root
    path=safe_under(root / row._mapping['relative_path'], root)
    if not path.exists() or not path.is_file(): raise HTTPException(404, 'File missing')
    return path, row._mapping['filename']
