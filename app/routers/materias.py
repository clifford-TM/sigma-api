from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Usuario, Materia, Curso

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
        .order_by(Materia.curso_id.asc(), Materia.semestre.asc(), Materia.nome.asc())
        .all()
    )

    cursos = db.query(Curso).all()
    mapa_cursos = {c.id_curso: c.nome for c in cursos}

    return templates.TemplateResponse(
        request=request,
        name="materias/index.html",
        context={
            "usuario": current_user,
            "materias": materias,
            "mapa_cursos": mapa_cursos,
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

    cursos = db.query(Curso).order_by(Curso.nome.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="materias/materia-form.html",
        context={
            "usuario": current_user,
            "materia": None,
            "cursos": cursos,
            "erro": None,
        },
    )


@router.post("/nova")
def criar_materia(
    request: Request,
    nome: str = Form(...),
    curso_id: int = Form(...),
    semestre: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    cursos = db.query(Curso).order_by(Curso.nome.asc()).all()
    curso = db.query(Curso).filter(Curso.id_curso == curso_id).first()

    if not curso:
        return templates.TemplateResponse(
            request=request,
            name="materias/materia-form.html",
            context={
                "usuario": current_user,
                "materia": None,
                "cursos": cursos,
                "erro": "Curso inválido.",
            },
        )

    try:
        materia = Materia(
            nome=nome.strip(),
            curso_id=curso.id_curso,
            semestre=semestre,
        )

        db.add(materia)
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
                "cursos": cursos,
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

    cursos = db.query(Curso).order_by(Curso.nome.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="materias/materia-form.html",
        context={
            "usuario": current_user,
            "materia": materia,
            "cursos": cursos,
            "erro": None,
        },
    )


@router.post("/{materia_id}/editar")
def editar_materia(
    materia_id: int,
    request: Request,
    nome: str = Form(...),
    curso_id: int = Form(...),
    semestre: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    materia = db.query(Materia).filter(Materia.id_materia == materia_id).first()
    cursos = db.query(Curso).order_by(Curso.nome.asc()).all()
    curso = db.query(Curso).filter(Curso.id_curso == curso_id).first()

    if not materia:
        return RedirectResponse(url="/materias/", status_code=303)

    if not curso:
        return templates.TemplateResponse(
            request=request,
            name="materias/materia-form.html",
            context={
                "usuario": current_user,
                "materia": materia,
                "cursos": cursos,
                "erro": "Curso inválido.",
            },
        )

    materia.nome = nome.strip()
    materia.curso_id = curso_id
    materia.semestre = semestre

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