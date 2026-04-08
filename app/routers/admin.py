from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.models import Usuario

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="public")


@router.get("/admin")
def admin_dashboard(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        if current_user.tipo == "professor":
            return RedirectResponse("/professor/dashboard", status_code=303)

        if current_user.tipo == "aluno":
            return RedirectResponse("/aluno/dashboard", status_code=303)

        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={"request": request, "usuario": current_user},
    )