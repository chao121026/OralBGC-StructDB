from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
from app.services.bgc_files import resolve_gbk
from app.services.downloads import resolve_download

router=APIRouter(tags=['downloads'])

@router.get('/downloads/file/{file_key}')
def download_file(file_key: str):
    path, filename = resolve_download(file_key)
    return FileResponse(path, filename=filename)


@router.get('/bgcs/gbk/{public_bgc_id}')
def bgc_gbk(public_bgc_id: str):
    content, filename = resolve_gbk(public_bgc_id)
    return Response(
        content,
        media_type="chemical/x-genbank",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
