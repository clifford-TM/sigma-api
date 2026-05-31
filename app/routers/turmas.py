from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import (
    Usuario, Turma, Curso, Materia,
    GradeCurricular, Professor, ProfessorMateria,
    TurmaMateriaProfessor
)

router = APIRouter(prefix="/turmas", tags=["turmas"])
templates = Jinja2Templates(directory="public")


@router.get("/")
def listar_turmas(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    turmas = (
        db.query(Turma)
        .order_by(Turma.ano.desc(), Turma.curso_id.asc(), Turma.semestre.asc())
        .all()
    )

    cursos = db.query(Curso).all()
    mapa_cursos = {c.id_curso: c.nome for c in cursos}

    return templates.TemplateResponse(
        request=request,
        name="turmas/turmas-lista.html",
        context={
            "usuario": current_user,
            "turmas": turmas,
            "mapa_cursos": mapa_cursos,
        },
    )


@router.get("/nova")
def nova_turma(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    cursos = db.query(Curso).order_by(Curso.nome.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="turmas/turma-form.html",
        context={
            "usuario": current_user,
            "turma": None,
            "cursos": cursos,
            "erro": None,
        },
    )


@router.post("/nova")
def criar_turma(
    request: Request,
    ano: int = Form(...),
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
            name="turmas/turma-form.html",
            context={
                "usuario": current_user,
                "turma": None,
                "cursos": cursos,
                "erro": "Curso inválido.",
            },
        )

    try:
        turma = Turma(
            ano=ano,
            curso_id=curso.id_curso,
            semestre=semestre,
        )

        db.add(turma)
        db.commit()

        return RedirectResponse(url="/turmas/", status_code=303)

    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="turmas/turma-form.html",
            context={
                "usuario": current_user,
                "turma": None,
                "cursos": cursos,
                "erro": f"Erro ao cadastrar turma: {e}",
            },
        )


@router.get("/{turma_id}/editar")
def editar_turma_form(
    turma_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    turma = db.query(Turma).filter(Turma.id_turma == turma_id).first()

    if not turma:
        return RedirectResponse(url="/turmas/", status_code=303)

    cursos = db.query(Curso).order_by(Curso.nome.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="turmas/turma-form.html",
        context={
            "usuario": current_user,
            "turma": turma,
            "cursos": cursos,
            "erro": None,
        },
    )


@router.post("/{turma_id}/editar")
def editar_turma(
    turma_id: int,
    request: Request,
    ano: int = Form(...),
    curso_id: int = Form(...),
    semestre: int = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    turma = db.query(Turma).filter(Turma.id_turma == turma_id).first()
    cursos = db.query(Curso).order_by(Curso.nome.asc()).all()
    curso = db.query(Curso).filter(Curso.id_curso == curso_id).first()

    if not turma:
        return RedirectResponse(url="/turmas/", status_code=303)

    if not curso:
        return templates.TemplateResponse(
            request=request,
            name="turmas/turma-form.html",
            context={
                "usuario": current_user,
                "turma": turma,
                "cursos": cursos,
                "erro": "Curso inválido.",
            },
        )

    turma.ano = ano
    turma.curso_id = curso_id
    turma.semestre = semestre

    db.commit()

    return RedirectResponse(url="/turmas/", status_code=303)


@router.post("/{turma_id}/excluir")
def excluir_turma(
    turma_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    turma = db.query(Turma).filter(Turma.id_turma == turma_id).first()

    if turma:
        db.delete(turma)
        db.commit()

    return RedirectResponse(url="/turmas/", status_code=303)

@router.get("/{turma_id}/gerenciar")
def gerenciar_turma(
    turma_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    turma = db.query(Turma).filter(Turma.id_turma == turma_id).first()
    if not turma:
        return RedirectResponse(url="/turmas/", status_code=303)

    curso = db.query(Curso).filter(Curso.id_curso == turma.curso_id).first()

    grade = (
        db.query(GradeCurricular, Materia)
        .join(Materia, Materia.id_materia == GradeCurricular.materia_id)
        .filter(
            GradeCurricular.curso_id == turma.curso_id,
            GradeCurricular.semestre == turma.semestre,
        )
        .order_by(Materia.nome.asc())
        .all()
    )

    professores_por_materia = {}
    for _, materia in grade:
        professores = (
            db.query(Professor, Usuario)
            .join(Usuario, Usuario.id_usuario == Professor.usuario_id)
            .join(ProfessorMateria, ProfessorMateria.professor_id == Professor.id_professor)
            .filter(ProfessorMateria.materia_id == materia.id_materia)
            .order_by(Usuario.nome.asc())
            .all()
        )
        professores_por_materia[materia.id_materia] = professores

    alocacoes = (
        db.query(TurmaMateriaProfessor)
        .filter(TurmaMateriaProfessor.turma_id == turma.id_turma)
        .all()
    )
    professor_selecionado = {
        a.materia_id: a.professor_id
        for a in alocacoes
    }

    return templates.TemplateResponse(
        request=request,
        name="turmas/turma-gerenciar.html",
        context={
            "usuario": current_user,
            "turma": turma,
            "curso": curso,
            "grade": grade,
            "professores_por_materia": professores_por_materia,
            "professor_selecionado": professor_selecionado,
        },
    )

@router.post("/{turma_id}/gerenciar")
async def salvar_gerenciamento_turma(
    turma_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)

    turma = db.query(Turma).filter(Turma.id_turma == turma_id).first()
    if not turma:
        return RedirectResponse(url="/turmas/", status_code=303)

    form = await request.form()

    grade = (
        db.query(GradeCurricular)
        .filter(
            GradeCurricular.curso_id == turma.curso_id,
            GradeCurricular.semestre == turma.semestre,
        )
        .all()
    )

    for item in grade:
        campo = f"professor_materia_{item.materia_id}"
        professor_id = form.get(campo)

        db.query(TurmaMateriaProfessor).filter(
            TurmaMateriaProfessor.turma_id == turma.id_turma,
            TurmaMateriaProfessor.materia_id == item.materia_id,
        ).delete()

        if professor_id:
            db.add(
                TurmaMateriaProfessor(
                    turma_id=turma.id_turma,
                    materia_id=item.materia_id,
                    professor_id=int(professor_id),
                )
            )

    db.commit()

    return RedirectResponse(url=f"/turmas/{turma_id}/gerenciar", status_code=303)