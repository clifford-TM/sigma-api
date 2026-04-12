from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Evento, Sala, Usuario

router = APIRouter(prefix="/professor", tags=["professor"])
templates = Jinja2Templates(directory="public")


def professor_autenticado(current_user: Usuario) -> bool:
    return current_user.tipo == "professor"


@router.get("/dashboard")
def dashboard_professor(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    proximos_eventos = (
        db.query(Evento)
        .filter(
            Evento.host == current_user.id_usuario,
            Evento.status.in_(["agendado", "pendente"]),
        )
        .order_by(Evento.inicio_previsto.asc())
        .limit(5)
        .all()
    )

    eventos_em_andamento = (
        db.query(Evento)
        .filter(
            Evento.host == current_user.id_usuario,
            Evento.status.in_(["ativo", "encerrando", "aguardando_validacao"]),
        )
        .order_by(Evento.inicio_previsto.asc())
        .limit(5)
        .all()
    )

    projetos_pendentes = (
        db.query(Evento)
        .filter(
            Evento.tipo == "projeto",
            Evento.autorizado_por == current_user.id_usuario,
            Evento.status == "pendente",
        )
        .order_by(Evento.inicio_previsto.asc())
        .limit(5)
        .all()
    )

    salas = {
        sala.id_sala: sala
        for sala in db.query(Sala).all()
    }

    return templates.TemplateResponse(
        request=request,
        name="professor/index.html",
        context={
            "usuario": current_user,
            "proximos_eventos": proximos_eventos,
            "eventos_em_andamento": eventos_em_andamento,
            "projetos_pendentes": projetos_pendentes,
            "salas": salas,
            "agora": datetime.now(),
        },
    )


@router.get("/projetos/{evento_id}/aprovar")
def aprovar_projeto(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.tipo == "projeto",
            Evento.autorizado_por == current_user.id_usuario,
            Evento.status == "pendente",
        )
        .first()
    )

    if not evento:
        return RedirectResponse(
            url="/professor/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    evento.status = "agendado"
    db.commit()

    return RedirectResponse(
        url="/professor/dashboard",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/projetos/{evento_id}/reprovar")
def formulario_reprovar_projeto(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.tipo == "projeto",
            Evento.autorizado_por == current_user.id_usuario,
            Evento.status == "pendente",
        )
        .first()
    )

    if not evento:
        return RedirectResponse(
            url="/professor/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request=request,
        name="professor/projeto-reprovar.html",
        context={
            "usuario": current_user,
            "evento": evento,
            "erro": None,
        },
    )


@router.post("/projetos/{evento_id}/reprovar")
def reprovar_projeto(
    evento_id: int,
    request: Request,
    motivo: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.tipo == "projeto",
            Evento.autorizado_por == current_user.id_usuario,
            Evento.status == "pendente",
        )
        .first()
    )

    if not evento:
        return RedirectResponse(
            url="/professor/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    motivo = motivo.strip()

    if not motivo:
        return templates.TemplateResponse(
            request=request,
            name="professor/projeto-reprovar.html",
            context={
                "usuario": current_user,
                "evento": evento,
                "erro": "Informe uma justificativa para reprovar o projeto.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    evento.status = "cancelado"
    evento.motivo_nao_realizacao = motivo
    db.commit()

    return RedirectResponse(
        url="/professor/dashboard",
        status_code=status.HTTP_303_SEE_OTHER,
    )