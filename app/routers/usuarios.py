from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import RFIDTag, Usuario, Aluno, Professor, Turma, Curso
from app.security import hash_password
import re

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
templates = Jinja2Templates(directory="public")

TIPOS_VALIDOS = {"aluno", "professor", "seguranca", "zelador", "tecnico", "admin"}

def somente_admin(current_user: Usuario) -> bool:
    return current_user.tipo == "admin"

@router.get("/")
def listar_usuarios(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    
    if not somente_admin(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    
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
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    
    if not somente_admin(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    
    turmas = (
        db.query(Turma)
        .order_by(
            Turma.ano.desc(),
            Turma.curso_id.asc(),
            Turma.semestre.asc(),
            Turma.periodo.asc(),
        )
        .all()
    )
    cursos = db.query(Curso).all()
    mapa_cursos = {c.id_curso: c.nome for c in cursos}

    return templates.TemplateResponse(
        request=request,
        name="usuarios/usuario-form.html",
        context={
            "usuario": current_user,
            "erro": None,
            "valores": {},
            "tipos": sorted(TIPOS_VALIDOS),
            "turmas": turmas,
            "mapa_cursos": mapa_cursos,
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
    turma_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not somente_admin(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    nome = nome.strip()
    email = email.strip().lower()
    senha = senha.strip()
    codigo_rfid = codigo_rfid.strip().upper()

    turmas = (
        db.query(Turma)
        .order_by(
            Turma.ano.desc(),
            Turma.curso_id.asc(),
            Turma.semestre.asc(),
            Turma.periodo.asc(),
        )
        .all()
    )
    cursos = db.query(Curso).all()
    mapa_cursos = {c.id_curso: c.nome for c in cursos}

    valores = {
        "nome": nome,
        "tipo": tipo,
        "email": email,
        "codigo_rfid": codigo_rfid,
        "turma_id": turma_id,
    }

    HEX_RE = re.compile(r"^[0-9A-F]{8,24}$")

    if not nome:
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "O nome é obrigatório.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
                "turmas": turmas,
                "mapa_cursos": mapa_cursos,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not email:
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "O email é obrigatório.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
                "turmas": turmas,
                "mapa_cursos": mapa_cursos,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(senha) < 8 or senha.isdigit() or senha.isalpha():
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "A senha deve ter pelo menos 8 caracteres e misturar letras com números ou símbolos.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
                "turmas": turmas,
                "mapa_cursos": mapa_cursos,
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
                "turmas": turmas,
                "mapa_cursos": mapa_cursos,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if codigo_rfid and not HEX_RE.match(codigo_rfid):
        return templates.TemplateResponse(
            request=request,
            name="usuarios/usuario-form.html",
            context={
                "usuario": current_user,
                "erro": "O código RFID inválido, verifique a TAG.",
                "valores": valores,
                "tipos": sorted(TIPOS_VALIDOS),
                "turmas": turmas,
                "mapa_cursos": mapa_cursos,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if tipo == "aluno":
        if turma_id is None:
            return templates.TemplateResponse(
                request=request,
                name="usuarios/usuario-form.html",
                context={
                    "usuario": current_user,
                    "erro": "Selecione a turma do aluno.",
                    "valores": valores,
                    "tipos": sorted(TIPOS_VALIDOS),
                    "turmas": turmas,
                    "mapa_cursos": mapa_cursos,
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        turma = db.query(Turma).filter(Turma.id_turma == turma_id).first()
        if not turma:
            return templates.TemplateResponse(
                request=request,
                name="usuarios/usuario-form.html",
                context={
                    "usuario": current_user,
                    "erro": "Turma inválida.",
                    "valores": valores,
                    "tipos": sorted(TIPOS_VALIDOS),
                    "turmas": turmas,
                    "mapa_cursos": mapa_cursos,
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
                "turmas": turmas,
                "mapa_cursos": mapa_cursos,
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
                    "turmas": turmas,
                    "mapa_cursos": mapa_cursos,
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

        if tipo == "aluno":
            db.add(Aluno(
                usuario_id=novo_usuario.id_usuario,
                turma_id=turma_id,
            ))

        if tipo == "professor":
            db.add(Professor(
                usuario_id=novo_usuario.id_usuario,
            ))

        if codigo_rfid:
            db.add(RFIDTag(
                usuario_id=novo_usuario.id_usuario,
                codigo=codigo_rfid,
                ativa=True,
            ))

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
                "turmas": turmas,
                "mapa_cursos": mapa_cursos,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/usuarios/", status_code=status.HTTP_303_SEE_OTHER)