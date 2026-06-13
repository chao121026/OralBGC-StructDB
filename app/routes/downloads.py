from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.services.downloads import resolve_download

router=APIRouter(tags=['downloads'])

@router.get('/downloads/file/{file_key}')
def download_file(file_key: str):
    path, filename = resolve_download(file_key)
    return FileResponse(path, filename=filename)
