from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.models import Usuario

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="public")


@router.get("/")
def home():
    return RedirectResponse(url="/login", status_code=303)


@router.get("/admin")
def admin_dashboard(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        if current_user.tipo == "professor":
            return RedirectResponse(url="/professor/dashboard", status_code=303)
        elif current_user.tipo == "aluno":
            return RedirectResponse(url="/aluno/dashboard", status_code=303)
        else:
            return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={"usuario": current_user},
    )