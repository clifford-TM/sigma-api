from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Usuario, Curso

router = APIRouter(prefix="/cursos", tags=["cursos"])
templates = Jinja2Templates(directory="public")


@router.get("/")
def listar_cursos(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    cursos = db.query(Curso).order_by(Curso.nome.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="cursos/index.html",
        context={
            "usuario": current_user,
            "cursos": cursos,
        },
    )


@router.get("/novo")
def novo_curso(
    request: Request,
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="cursos/curso-form.html",
        context={
            "usuario": current_user,
            "curso": None,
            "erro": None,
        },
    )


@router.post("/novo")
def criar_curso(
    request: Request,
    nome: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    nome = nome.strip()

    if not nome:
        return templates.TemplateResponse(
            request=request,
            name="cursos/curso-form.html",
            context={
                "usuario": current_user,
                "curso": None,
                "erro": "Informe o nome do curso.",
            },
        )

    try:
        curso = Curso(nome=nome)
        db.add(curso)
        db.commit()

        return RedirectResponse(url="/cursos/", status_code=303)

    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="cursos/curso-form.html",
            context={
                "usuario": current_user,
                "curso": None,
                "erro": f"Erro ao cadastrar curso: {e}",
            },
        )


@router.get("/{curso_id}/editar")
def editar_curso_form(
    curso_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    curso = db.query(Curso).filter(Curso.id_curso == curso_id).first()

    if not curso:
        return RedirectResponse(url="/cursos/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="cursos/curso-form.html",
        context={
            "usuario": current_user,
            "curso": curso,
            "erro": None,
        },
    )


@router.post("/{curso_id}/editar")
def editar_curso(
    curso_id: int,
    nome: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    curso = db.query(Curso).filter(Curso.id_curso == curso_id).first()

    if not curso:
        return RedirectResponse(url="/cursos/", status_code=303)

    curso.nome = nome.strip()
    db.commit()

    return RedirectResponse(url="/cursos/", status_code=303)


@router.post("/{curso_id}/excluir")
def excluir_curso(
    curso_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    curso = db.query(Curso).filter(Curso.id_curso == curso_id).first()

    if curso:
        db.delete(curso)
        db.commit()

    return RedirectResponse(url="/cursos/", status_code=303)