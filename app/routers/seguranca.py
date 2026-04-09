# app/routers/seguranca.py

from datetime import datetime

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Evento, Sala, Usuario

router = APIRouter(prefix="/seguranca", tags=["seguranca"])
templates = Jinja2Templates(directory="public")


def usuario_eh_seguranca(usuario: Usuario) -> bool:
    return usuario.tipo == "seguranca"


@router.get("/dashboard")
def dashboard_seguranca(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    agora = datetime.now()

    proximos_eventos = (
        db.query(Evento)
        .filter(
            Evento.status.in_(["agendado", "pendente"]),
            Evento.inicio_previsto > agora
        )
        .order_by(Evento.inicio_previsto.asc())
        .all()
    )

    eventos_em_andamento = (
        db.query(Evento)
        .filter(
            Evento.status.in_(["ativo", "encerrando"])
        )
        .order_by(Evento.inicio_previsto.asc())
        .all()
    )

    aguardando_validacao = (
        db.query(Evento)
        .filter(Evento.status == "aguardando_validacao")
        .order_by(Evento.fim_previsto.asc())
        .all()
    )

    salas = {
        sala.id_sala: sala
        for sala in db.query(Sala).all()
    }

    usuarios = {
        usuario.id_usuario: usuario
        for usuario in db.query(Usuario).all()
    }

    return templates.TemplateResponse(
        "seguranca/dashboard.html",
        {
            "request": request,
            "usuario": current_user,
            "proximos_eventos": proximos_eventos,
            "eventos_em_andamento": eventos_em_andamento,
            "aguardando_validacao": aguardando_validacao,
            "salas": salas,
            "usuarios": usuarios,
        }
    )


@router.get("/salas")
def visao_geral_salas(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    eventos_ativos = (
        db.query(Evento)
        .filter(
            Evento.status.in_(
                ["agendado", "pendente", "ativo", "encerrando", "aguardando_validacao"]
            )
        )
        .all()
    )

    usuarios = {
        usuario.id_usuario: usuario
        for usuario in db.query(Usuario).all()
    }

    eventos_por_sala = {}

    for evento in eventos_ativos:
        if evento.sala_id not in eventos_por_sala:
            eventos_por_sala[evento.sala_id] = []

        eventos_por_sala[evento.sala_id].append(evento)

    return templates.TemplateResponse(
        "seguranca/salas.html",
        {
            "request": request,
            "usuario": current_user,
            "salas": salas,
            "eventos_por_sala": eventos_por_sala,
            "usuarios": usuarios,
        }
    )

@router.get("/validacoes")
def listar_validacoes(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    eventos = (
        db.query(Evento)
        .filter(Evento.status == "aguardando_validacao")
        .order_by(Evento.fim_previsto.asc())
        .all()
    )

    salas = {
        sala.id_sala: sala
        for sala in db.query(Sala).all()
    }

    usuarios = {
        usuario.id_usuario: usuario
        for usuario in db.query(Usuario).all()
    }

    return templates.TemplateResponse(
        "seguranca/validacoes-lista.html",
        {
            "request": request,
            "usuario": current_user,
            "eventos": eventos,
            "salas": salas,
            "usuarios": usuarios,
        }
    )


@router.get("/validacoes/{evento_id}")
def formulario_validacao(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER
        )

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.status == "aguardando_validacao"
        )
        .first()
    )

    if not evento:
        return RedirectResponse(
            url="/seguranca/validacoes",
            status_code=status.HTTP_303_SEE_OTHER
        )

    sala = (
        db.query(Sala)
        .filter(Sala.id_sala == evento.sala_id)
        .first()
    )

    host = (
        db.query(Usuario)
        .filter(Usuario.id_usuario == evento.host)
        .first()
    )

    return templates.TemplateResponse(
        "seguranca/validacao-form.html",
        {
            "request": request,
            "usuario": current_user,
            "evento": evento,
            "sala": sala,
            "host": host,
            "erro": None,
        }
    )