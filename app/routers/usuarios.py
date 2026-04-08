from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Usuario
from app.security import hash_password

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
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    valores = {"nome": nome, "tipo": tipo, "email": email}

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

    existe = db.query(Usuario).filter(Usuario.email == email).first()
    if existe:
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

    novo_usuario = Usuario(
        nome=nome.strip(),
        tipo=tipo,
        email=email.strip().lower(),
        senha=hash_password(senha),
    )

    db.add(novo_usuario)
    db.commit()

    return RedirectResponse(url="/usuarios", status_code=status.HTTP_303_SEE_OTHER)