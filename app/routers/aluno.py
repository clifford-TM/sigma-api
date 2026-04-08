from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Usuario, Evento, Presenca

router = APIRouter(prefix="/aluno", tags=["aluno"])
templates = Jinja2Templates(directory="public")


@router.get("/dashboard")
def dashboard_aluno(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "aluno":
        return RedirectResponse(url="/dashboard", status_code=303)

    presencas_recentes = (
        db.query(Presenca)
        .filter(Presenca.id_usuario == current_user.id_usuario)
        .order_by(Presenca.data_hora.desc())
        .limit(5)
        .all()
    )

    projetos = (
        db.query(Evento)
        .join(
            __import__("app.models", fromlist=["EventoParticipante"]).EventoParticipante,
            __import__("app.models", fromlist=["EventoParticipante"]).EventoParticipante.evento_id == Evento.id_evento
        )
        .filter(
            Evento.tipo == "projeto",
            __import__("app.models", fromlist=["EventoParticipante"]).EventoParticipante.usuario_id == current_user.id_usuario
        )
        .order_by(Evento.inicio_previsto.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="aluno/dashboard.html",
        context={
            "usuario": current_user,
            "presencas_recentes": presencas_recentes,
            "projetos": projetos,
        },
    )