from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Evento, Sala, Usuario

router = APIRouter(prefix="/zelador", tags=["zelador"])
templates = Jinja2Templates(directory="public")

@router.get("/dashboard")
def dashboard_zelador(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="operacional/index.html",
        context={
            "usuario": current_user,
            "titulo": "Painel de zeladoria",
            "tipo_evento_principal": "limpeza",
        },
    )