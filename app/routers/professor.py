from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Usuario, Evento

router = APIRouter(prefix="/professor", tags=["professor"])
templates = Jinja2Templates(directory="public")


@router.get("/dashboard")
def dashboard_professor(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "professor":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard", status_code=303)
    
    proximos_eventos = []
    eventos_em_andamento = []
    projetos_pendentes = []

    if current_user.tipo == "professor":
        proximos_eventos = (
            db.query(Evento)
            .filter(
                Evento.host == current_user.id_usuario,
                Evento.status.in_(["agendado", "pendente"])
            )
            .order_by(Evento.inicio_previsto.asc())
            .limit(5)
            .all()
        )

        eventos_em_andamento = (
            db.query(Evento)
            .filter(
                Evento.host == current_user.id_usuario,
                Evento.status.in_(["ativo", "encerrando", "aguardando_validacao"])
            )
            .order_by(Evento.inicio_real.asc())
            .limit(5)
            .all()
        )

        projetos_pendentes = (
            db.query(Evento)
            .filter(
                Evento.tipo == "projeto",
                Evento.autorizado_por == current_user.id_usuario,
                Evento.status == "pendente"
            )
            .order_by(Evento.inicio_previsto.asc())
            .limit(5)
            .all()
        )

    return templates.TemplateResponse(
        request=request,
        name="professor/dashboard.html",
        context={
            "usuario": current_user,
            "proximos_eventos": proximos_eventos,
            "eventos_em_andamento": eventos_em_andamento,
            "projetos_pendentes": projetos_pendentes,
            "agora": datetime.now(),
        },
    )