from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.services.structure_files import resolve_cif

router=APIRouter(tags=['structures'])

@router.get('/structures/cif/{public_protein_id:path}')
def cif(public_protein_id: str):
    path, filename = resolve_cif(public_protein_id)
    return FileResponse(path, media_type='chemical/x-cif', filename=filename)
