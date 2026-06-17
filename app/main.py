from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.routes import api, pages, downloads, structures
from app.templates_env import templates
from app.config import get_settings
from app.database import db_connect

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_resource_delivery()
    with db_connect() as conn:
        conn.exec_driver_sql("select 1")
    print(f"{settings.public_name} application started in {settings.deployment_mode} mode")
    yield


settings = get_settings()
app = FastAPI(title=settings.public_name, version='0.1.0', description=settings.subtitle, lifespan=lifespan)
app.mount('/static', StaticFiles(directory='app/static'), name='static')
app.include_router(api.router)
app.include_router(structures.router)
app.include_router(downloads.router)
app.include_router(pages.router)

@app.get('/health', include_in_schema=False)
def health():
    database = "available"
    try:
        with db_connect() as conn:
            conn.exec_driver_sql("select 1")
    except Exception:
        database = "unavailable"
    return {
        "status": "ok" if database == "available" else "degraded",
        "database": database,
        "deployment_mode": get_settings().deployment_mode,
    }

@app.exception_handler(404)
def not_found(request: Request, exc):
    return templates.TemplateResponse('errors/404.html', {"request":request, "detail":getattr(exc,'detail','Not found')}, status_code=404)

@app.exception_handler(500)
def server_error(request: Request, exc):
    return templates.TemplateResponse('errors/500.html', {"request":request}, status_code=500)
