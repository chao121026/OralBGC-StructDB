from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.services.structure_files import resolve_cif

router=APIRouter(tags=['structures'])

@router.get('/structures/cif/{public_identifier:path}')
def cif(public_identifier: str):
    path, filename = resolve_cif(public_identifier)
    return FileResponse(path, media_type='chemical/x-cif', filename=filename)
