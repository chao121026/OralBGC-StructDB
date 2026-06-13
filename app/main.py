from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.routes import api, pages, downloads, structures

app = FastAPI(title='PHRC_BGCStructDB', version='0.1.0', description='Public structure-enabled BGC protein database for oral microbiome MAGs')
app.mount('/static', StaticFiles(directory='app/static'), name='static')
app.include_router(api.router)
app.include_router(structures.router)
app.include_router(downloads.router)
app.include_router(pages.router)

templates=Jinja2Templates(directory='app/templates')

@app.exception_handler(404)
def not_found(request: Request, exc):
    return templates.TemplateResponse('errors/404.html', {"request":request, "detail":getattr(exc,'detail','Not found')}, status_code=404)

@app.exception_handler(500)
def server_error(request: Request, exc):
    return templates.TemplateResponse('errors/500.html', {"request":request}, status_code=500)
