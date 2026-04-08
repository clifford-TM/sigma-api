from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import RFIDTag, Usuario
from app.security import hash_password
import re

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
templates = Jinja2Templates(directory="public")

TIPOS_VALIDOS = {"aluno", "professor", "seguranca", "tecnico", "admin"}


@router.get("/")
def listar_usuarios(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    usuarios = db.query(Usuario).order_by(Usuario.nome.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="usuarios/usuarios-lista.html",
        context={
            "usuario": current_user,
            "usuarios": usuarios,
        },
    )


@router.get("/novo")
def novo_usuario_form(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request=request,
        name="usuarios/usuario-form.html",
        context={
            "usuario": current_user,
            "erro": None,
            "valores": {},
            "tipos": sorted(TIPOS_VALIDOS),
        },
    )


@router.post("/")
def criar_usuario(
    request: Request,
    nome: str = Form(...),
    tipo: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    codigo_rfid: str = Form(""),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    nome = nome.strip()
    email = email.strip().lower()
    codigo_rfid = codigo_rfid.strip().upper()

    valores = {
        "nome": nome,
        "tipo": tipo,
        "email": email,
        "codigo_rfid": codigo_rfid,
    }

    HEX_RE = re.compile(r"^[0-9A-F]{8,24}$")

    if codigo_rfid and not HEX_RE.match(codigo_rfid):
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "O código RFID inválido, verifique a TAG",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not nome:
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "O nome é obrigatório.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if tipo not in TIPOS_VALIDOS:
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "Tipo de usuário inválido.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(senha) < 6:
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "A senha deve ter pelo menos 6 caracteres.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    existe_email = db.query(Usuario).filter(Usuario.email == email).first()
    if existe_email:
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "Já existe um usuário com esse email.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if codigo_rfid:
        existe_rfid = db.query(RFIDTag).filter(RFIDTag.codigo == codigo_rfid).first()
        if existe_rfid:
            return templates.TemplateResponse(
                request=request,
                name="usuarios/usuario-form.html",
                context={
                    "usuario": current_user,
                    "erro": "Esse código RFID já está cadastrado.",
                    "valores": valores,
                    "tipos": sorted(TIPOS_VALIDOS),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    try:
        novo_usuario = Usuario(
            nome=nome,
            tipo=tipo,
            email=email,
            senha=hash_password(senha),
        )

        db.add(novo_usuario)
        db.flush()

        if codigo_rfid:
            nova_tag = RFIDTag(
                usuario_id=novo_usuario.id_usuario,
                codigo=codigo_rfid,
                ativa=True,
            )
            db.add(nova_tag)

        db.commit()

    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "Não foi possível salvar o usuário. Verifique os dados informados.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/usuarios", status_code=status.HTTP_303_SEE_OTHER)