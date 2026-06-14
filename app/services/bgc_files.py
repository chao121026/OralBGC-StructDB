import tarfile

from fastapi import HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.database import db_connect, table_exists
from app.security import reject_unsafe_identifier, safe_under


def resolve_gbk(public_bgc_id: str) -> tuple[bytes, str]:
    reject_unsafe_identifier(public_bgc_id)
    with db_connect() as conn:
        if not table_exists(conn, "bgc_gbk_map"):
            raise HTTPException(404, "No BGC GenBank map")
        row = conn.execute(
            text("""select archive_path, member_name, filename
                    from bgc_gbk_map
                    where public_bgc_id=:id and public_safe=1"""),
            {"id": public_bgc_id},
        ).first()
    if not row:
        raise HTTPException(404, "BGC GenBank record not found")
    root = get_settings().resolve_package_root()
    archive = safe_under(root / row._mapping["archive_path"], root / "antismash")
    if not archive.exists():
        raise HTTPException(404, "BGC GenBank archive missing")
    member_name = row._mapping["member_name"]
    if "/" in member_name or not member_name.endswith(".gbk"):
        raise HTTPException(403, "Unsafe BGC GenBank member")
    with tarfile.open(archive, "r:gz") as tar:
        try:
            member = tar.getmember(member_name)
        except KeyError as exc:
            raise HTTPException(404, "BGC GenBank member missing") from exc
        if not member.isfile() or member.name != member_name:
            raise HTTPException(403, "Unsafe BGC GenBank member")
        handle = tar.extractfile(member)
        if handle is None:
            raise HTTPException(404, "BGC GenBank member missing")
        return handle.read(), row._mapping["filename"]
