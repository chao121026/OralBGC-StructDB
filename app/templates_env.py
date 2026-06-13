from fastapi.templating import Jinja2Templates

from app.template_filters import register_template_filters


templates = Jinja2Templates(directory="app/templates")
register_template_filters(templates)
