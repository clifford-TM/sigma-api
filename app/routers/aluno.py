from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Evento, Sala, Usuario

router = APIRouter(prefix="/aluno", tags=["aluno"])
templates = Jinja2Templates(directory="public")


def aluno_autenticado(current_user: Usuario) -> bool:
    return current_user.tipo == "aluno"


@router.get("/dashboard")
def dashboard_aluno(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not aluno_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    projetos = (
        db.query(Evento)
        .filter(
            Evento.host == current_user.id_usuario,
            Evento.tipo == "projeto",
        )
        .order_by(Evento.inicio_previsto.desc())
        .all()
    )

    salas = {sala.id_sala: sala for sala in db.query(Sala).all()}
    professores = {
        professor.id_usuario: professor
        for professor in db.query(Usuario).filter(Usuario.tipo == "professor").all()
    }

    return templates.TemplateResponse(
        request=request,
        name="aluno/index.html",
        context={
            "usuario": current_user,
            "projetos": projetos,
            "salas": salas,
            "professores": professores,
        },
    )


@router.get("/projetos")
def listar_projetos_aluno(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not aluno_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    projetos = (
        db.query(Evento)
        .filter(
            Evento.host == current_user.id_usuario,
            Evento.tipo == "projeto",
        )
        .order_by(Evento.inicio_previsto.desc())
        .all()
    )

    salas = {sala.id_sala: sala for sala in db.query(Sala).all()}
    professores = {
        professor.id_usuario: professor
        for professor in db.query(Usuario).filter(Usuario.tipo == "professor").all()
    }

    return templates.TemplateResponse(
        request=request,
        name="aluno/projetos-lista.html",
        context={
            "usuario": current_user,
            "projetos": projetos,
            "salas": salas,
            "professores": professores,
        },
    )


@router.get("/projetos/novo")
def formulario_novo_projeto(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not aluno_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()
    professores = (
        db.query(Usuario)
        .filter(Usuario.tipo == "professor")
        .order_by(Usuario.nome.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="aluno/projeto-form.html",
        context={
            "usuario": current_user,
            "erro": None,
            "valores": {},
            "salas": salas,
            "professores": professores,
        },
    )


@router.post("/projetos")
def criar_projeto_aluno(
    request: Request,
    sala_id: int = Form(...),
    autorizado_por: int = Form(...),
    descricao: str = Form(""),
    inicio_previsto: str = Form(...),
    fim_previsto: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not aluno_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    descricao = descricao.strip()

    valores = {
        "sala_id": sala_id,
        "autorizado_por": autorizado_por,
        "descricao": descricao,
        "inicio_previsto": inicio_previsto,
        "fim_previsto": fim_previsto,
    }

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()
    professores = (
        db.query(Usuario)
        .filter(Usuario.tipo == "professor")
        .order_by(Usuario.nome.asc())
        .all()
    )

    sala = db.query(Sala).filter(Sala.id_sala == sala_id).first()
    if not sala:
        return templates.TemplateResponse(
            request=request,
            name="aluno/projeto-form.html",
            context={
                "usuario": current_user,
                "erro": "A sala selecionada não existe.",
                "valores": valores,
                "salas": salas,
                "professores": professores,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    professor = (
        db.query(Usuario)
        .filter(
            Usuario.id_usuario == autorizado_por,
            Usuario.tipo == "professor",
        )
        .first()
    )
    if not professor:
        return templates.TemplateResponse(
            request=request,
            name="aluno/projeto-form.html",
            context={
                "usuario": current_user,
                "erro": "O professor autorizador é inválido.",
                "valores": valores,
                "salas": salas,
                "professores": professores,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        inicio_dt = datetime.fromisoformat(inicio_previsto)
        fim_dt = datetime.fromisoformat(fim_previsto)
    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="aluno/projeto-form.html",
            context={
                "usuario": current_user,
                "erro": "Data ou horário inválido.",
                "valores": valores,
                "salas": salas,
                "professores": professores,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if fim_dt <= inicio_dt:
        return templates.TemplateResponse(
            request=request,
            name="aluno/projeto-form.html",
            context={
                "usuario": current_user,
                "erro": "O horário de término deve ser posterior ao horário de início.",
                "valores": valores,
                "salas": salas,
                "professores": professores,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    conflito = (
        db.query(Evento)
        .filter(
            Evento.sala_id == sala_id,
            Evento.status.in_(["agendado", "ativo", "pendente"]),
            Evento.inicio_previsto < fim_dt,
            Evento.fim_previsto > inicio_dt,
        )
        .first()
    )

    if conflito:
        return templates.TemplateResponse(
            request=request,
            name="aluno/projeto-form.html",
            context={
                "usuario": current_user,
                "erro": "Já existe um evento agendado nessa sala para esse horário.",
                "valores": valores,
                "salas": salas,
                "professores": professores,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    novo_evento = Evento(
        tipo="projeto",
        host=current_user.id_usuario,
        autorizado_por=autorizado_por,
        forma_inicio="app",
        confirmado_por_rfid=False,
        motivo_nao_realizacao=None,
        sala_id=sala_id,
        status="pendente",
        descricao=descricao if descricao else None,
        inicio_previsto=inicio_dt,
        fim_previsto=fim_dt,
        inicio_real=None,
        fim_real=None,
    )

    db.add(novo_evento)
    db.commit()

    return RedirectResponse(
        url="/aluno/projetos",
        status_code=status.HTTP_303_SEE_OTHER,
    )