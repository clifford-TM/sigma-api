from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Usuario, Curso, Materia, GradeCurricular

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
        name="cursos/cursos-lista.html",
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
    codigo: str = Form(...),
    nome: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    codigo = codigo.strip().upper()
    nome = nome.strip()

    if not codigo or not nome:
        return templates.TemplateResponse(
            request=request,
            name="cursos/curso-form.html",
            context={
                "usuario": current_user,
                "curso": None,
                "erro": "Informe o código e o nome do curso.",
            },
        )

    try:
        curso = Curso(codigo=codigo, nome=nome)
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
    codigo: str = Form(...),
    nome: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    curso = db.query(Curso).filter(Curso.id_curso == curso_id).first()

    if not curso:
        return RedirectResponse(url="/cursos/", status_code=303)

    curso.codigo = codigo.strip().upper()
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

@router.get("/{curso_id}/grade")
def gerenciar_grade_curso(
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

    materias = db.query(Materia).order_by(Materia.nome.asc()).all()

    grade = (
        db.query(GradeCurricular)
        .filter(GradeCurricular.curso_id == curso_id)
        .order_by(GradeCurricular.semestre.asc(), GradeCurricular.materia_id.asc())
        .all()
    )

    materias_por_id = {m.id_materia: m for m in materias}

    return templates.TemplateResponse(
        request=request,
        name="cursos/cursos-grade.html",
        context={
            "usuario": current_user,
            "curso": curso,
            "materias": materias,
            "grade": grade,
            "materias_por_id": materias_por_id,
            "erro": None,
        },
    )

@router.post("/{curso_id}/grade/adicionar")
def adicionar_materia_grade(
    curso_id: int,
    materia_id: int = Form(...),
    semestre: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    try:
        item = GradeCurricular(
            curso_id=curso_id,
            materia_id=materia_id,
            semestre=semestre,
        )

        db.add(item)
        db.commit()

    except Exception:
        db.rollback()

    return RedirectResponse(url=f"/cursos/{curso_id}/grade", status_code=303)

@router.post("/{curso_id}/grade/{materia_id}/remover")
def remover_materia_grade(
    curso_id: int,
    materia_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    item = (
        db.query(GradeCurricular)
        .filter(
            GradeCurricular.curso_id == curso_id,
            GradeCurricular.materia_id == materia_id,
        )
        .first()
    )

    if item:
        db.delete(item)
        db.commit()

    return RedirectResponse(url=f"/cursos/{curso_id}/grade", status_code=303)