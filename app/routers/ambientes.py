from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Sala, EstadoSala, Usuario

router = APIRouter(prefix="/ambientes", tags=["ambientes"])
templates = Jinja2Templates(directory="public")

TIPOS_SALA = {"sala", "laboratorio", "auditorio"}


@router.get("/salas")
def listar_salas(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()
    estados = {e.id_estado_sala: e for e in db.query(EstadoSala).all()}

    return templates.TemplateResponse(
        request=request,
        name="ambientes/salas-lista.html",
        context={
            "usuario": current_user,
            "salas": salas,
            "estados": estados,
        },
    )


@router.get("/salas/nova")
def nova_sala_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    estados = db.query(EstadoSala).order_by(EstadoSala.nome.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="ambientes/sala-form.html",
        context={
            "usuario": current_user,
            "erro": None,
            "valores": {},
            "tipos": sorted(TIPOS_SALA),
            "estados": estados,
        },
    )


@router.post("/salas")
def criar_sala(
    request: Request,
    numero: str = Form(...),
    tipo: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/admin", status_code=303)

    numero = numero.strip()
    estado_inicial = 1

    valores = {
        "numero": numero,
        "tipo": tipo,
    }

    estados = db.query(EstadoSala).order_by(EstadoSala.nome.asc()).all()

    if not numero:
        return templates.TemplateResponse(
            request=request,
            name="ambientes/sala-form.html",
            context={
                "usuario": current_user,
                "erro": "Informe o número ou nome da sala.",
                "valores": valores,
                "tipos": sorted(TIPOS_SALA),
                "estados": estados,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if tipo not in TIPOS_SALA:
        return templates.TemplateResponse(
            request=request,
            name="ambientes/sala-form.html",
            context={
                "usuario": current_user,
                "erro": "Tipo de sala inválido.",
                "valores": valores,
                "tipos": sorted(TIPOS_SALA),
                "estados": estados,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        nova_sala = Sala(
            numero=numero,
            tipo=tipo,
            estado_atual_id=estado_inicial,
        )
        db.add(nova_sala)
        db.commit()

    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="ambientes/sala-form.html",
            context={
                "usuario": current_user,
                "erro": "Já existe uma sala cadastrada com esse identificador.",
                "valores": valores,
                "tipos": sorted(TIPOS_SALA),
                "estados": estados,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/ambientes/salas", status_code=status.HTTP_303_SEE_OTHER)