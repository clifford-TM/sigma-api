from typing import List

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Usuario, Materia, Professor, ProfessorMateria

router = APIRouter(prefix="/materias", tags=["materias"])
templates = Jinja2Templates(directory="public")


@router.get("/")
def listar_materias(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    materias = (
        db.query(Materia)
        .order_by(Materia.codigo.asc(), Materia.nome.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="materias/index.html",
        context={
            "usuario": current_user,
            "materias": materias,
        },
    )


@router.get("/nova")
def nova_materia(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    professores = (
        db.query(Professor, Usuario)
        .join(Usuario, Usuario.id_usuario == Professor.usuario_id)
        .order_by(Usuario.nome.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="materias/materia-form.html",
        context={
            "usuario": current_user,
            "materia": None,
            "professores": professores,
            "professores_selecionados": [],
            "erro": None,
        },
    )


@router.post("/nova")
def criar_materia(
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    professores_ids: List[int] = Form([]),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    codigo = codigo.strip().upper()
    nome = nome.strip()

    professores = (
        db.query(Professor, Usuario)
        .join(Usuario, Usuario.id_usuario == Professor.usuario_id)
        .order_by(Usuario.nome.asc())
        .all()
    )

    try:
        materia = Materia(
            codigo=codigo,
            nome=nome,
        )

        db.add(materia)
        db.flush()

        for professor_id in professores_ids:
            db.add(
                ProfessorMateria(
                    professor_id=professor_id,
                    materia_id=materia.id_materia,
                )
            )

        db.commit()
        return RedirectResponse(url="/materias/", status_code=303)

    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="materias/materia-form.html",
            context={
                "usuario": current_user,
                "materia": None,
                "professores": professores,
                "professores_selecionados": professores_ids,
                "erro": f"Erro ao cadastrar matéria: {e}",
            },
        )


@router.get("/{materia_id}/editar")
def editar_materia_form(
    materia_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    materia = db.query(Materia).filter(Materia.id_materia == materia_id).first()

    if not materia:
        return RedirectResponse(url="/materias/", status_code=303)

    professores = (
        db.query(Professor, Usuario)
        .join(Usuario, Usuario.id_usuario == Professor.usuario_id)
        .order_by(Usuario.nome.asc())
        .all()
    )

    professores_selecionados = [
        item.professor_id
        for item in db.query(ProfessorMateria)
        .filter(ProfessorMateria.materia_id == materia.id_materia)
        .all()
    ]

    return templates.TemplateResponse(
        request=request,
        name="materias/materia-form.html",
        context={
            "usuario": current_user,
            "materia": materia,
            "professores": professores,
            "professores_selecionados": professores_selecionados,
            "erro": None,
        },
    )


@router.post("/{materia_id}/editar")
def editar_materia(
    materia_id: int,
    request: Request,
    codigo: str = Form(...),
    nome: str = Form(...),
    professores_ids: List[int] = Form([]),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    materia = db.query(Materia).filter(Materia.id_materia == materia_id).first()

    professores = (
        db.query(Professor, Usuario)
        .join(Usuario, Usuario.id_usuario == Professor.usuario_id)
        .order_by(Usuario.nome.asc())
        .all()
    )

    if not materia:
        return RedirectResponse(url="/materias/", status_code=303)

    materia.codigo = codigo.strip().upper()
    materia.nome = nome.strip()

    db.query(ProfessorMateria).filter(
        ProfessorMateria.materia_id == materia.id_materia
    ).delete()

    for professor_id in professores_ids:
        db.add(
            ProfessorMateria(
                professor_id=professor_id,
                materia_id=materia.id_materia,
            )
        )

    db.commit()

    return RedirectResponse(url="/materias/", status_code=303)


@router.post("/{materia_id}/excluir")
def excluir_materia(
    materia_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    materia = db.query(Materia).filter(Materia.id_materia == materia_id).first()

    if materia:
        db.delete(materia)
        db.commit()

    return RedirectResponse(url="/materias/", status_code=303)