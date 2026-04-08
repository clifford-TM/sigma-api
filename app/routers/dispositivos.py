import re

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Dispositivo, Sala, Usuario

router = APIRouter(prefix="/dispositivos", tags=["dispositivos"])
templates = Jinja2Templates(directory="public")

IDENT_RE = re.compile(r"^[a-zA-Z0-9_-]{3,80}$")


@router.get("/")
def listar_dispositivos(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/admin", status_code=303)

    dispositivos = db.query(Dispositivo).order_by(Dispositivo.nome.asc()).all()
    salas = {s.id_sala: s for s in db.query(Sala).all()}

    return templates.TemplateResponse(
        request=request,
        name="dispositivos/dispositivos-lista.html",
        context={
            "usuario": current_user,
            "dispositivos": dispositivos,
            "salas": salas,
        },
    )


@router.get("/novo")
def novo_dispositivo_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/admin", status_code=303)

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="dispositivos/dispositivo-form.html",
        context={
            "usuario": current_user,
            "erro": None,
            "valores": {},
            "salas": salas,
        },
    )


@router.post("/")
def criar_dispositivo(
    request: Request,
    nome: str = Form(...),
    identificador_fisico: str = Form(...),
    sala_id: int = Form(...),
    ativo: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/admin", status_code=303)

    nome = nome.strip()
    identificador_fisico = identificador_fisico.strip()
    ativo_bool = ativo == "on"

    valores = {
        "nome": nome,
        "identificador_fisico": identificador_fisico,
        "sala_id": sala_id,
        "ativo": ativo_bool,
    }

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    if not nome:
        return templates.TemplateResponse(
            request=request,
            name="dispositivos/dispositivo-form.html",
            context={
                "usuario": current_user,
                "erro": "Informe o nome do dispositivo.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not IDENT_RE.match(identificador_fisico):
        return templates.TemplateResponse(
            request=request,
            name="dispositivos/dispositivo-form.html",
            context={
                "usuario": current_user,
                "erro": "Verifique o identificador físico. Use apenas letras, números, hífen e underline.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    sala = db.query(Sala).filter(Sala.id_sala == sala_id).first()
    if not sala:
        return templates.TemplateResponse(
            request=request,
            name="dispositivos/dispositivo-form.html",
            context={
                "usuario": current_user,
                "erro": "Sala inválida.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    dispositivo_existente = (
    db.query(Dispositivo)
    .filter(Dispositivo.sala_id == sala_id)
    .first())

    if dispositivo_existente:
        return templates.TemplateResponse(
            request=request,
            name="dispositivos/dispositivo-form.html",
            context={
                "usuario": current_user,
                "erro": "Já existe um dispositivo cadastrado para essa sala.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        novo_dispositivo = Dispositivo(
            nome=nome,
            identificador_fisico=identificador_fisico,
            sala_id=sala_id,
            ativo=ativo_bool,
        )
        db.add(novo_dispositivo)
        db.commit()

    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="dispositivos/dispositivo-form.html",
            context={
                "usuario": current_user,
                "erro": "Já existe um dispositivo com esse identificador físico.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/dispositivos", status_code=status.HTTP_303_SEE_OTHER)