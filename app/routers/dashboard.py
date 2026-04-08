from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.models import Usuario

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="public")


@router.get("/")
def home():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login", status_code=303)


@router.get("/dashboard")
def dashboard(request: Request, current_user: Usuario = Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={"usuario": current_user},
    )