from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.template_filters import register_template_filters


def branding_context(request: Request) -> dict:
    settings = get_settings()
    return {"brand": settings.branding, "preview_message": settings.preview_message}


templates = Jinja2Templates(directory="app/templates", context_processors=[branding_context])
register_template_filters(templates)
templates.env.globals["brand"] = get_settings().branding
