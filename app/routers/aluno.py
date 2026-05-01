from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Evento, Sala, Usuario, Presenca

router = APIRouter(prefix="/aluno", tags=["aluno"])
templates = Jinja2Templates(directory="public")


def aluno_autenticado(current_user: Usuario) -> bool:
    return current_user.tipo == "aluno"


@router.get("/dashboard")
def dashboard_aluno(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not aluno_autenticado(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    projetos = (
        db.query(Evento)
        .filter(
            Evento.host == current_user.id_usuario,
            Evento.tipo == "projeto",
        )
        .order_by(Evento.inicio_previsto.desc())
        .all()
    )

    salas = {
        sala.id_sala: sala
        for sala in db.query(Sala).all()
    }

    professores = {
        professor.id_usuario: professor
        for professor in db.query(Usuario)
        .filter(Usuario.tipo == "professor")
        .all()
    }

    entradas = (
        db.query(Presenca)
        .filter(
            Presenca.id_usuario == current_user.id_usuario,
            Presenca.tipo == "entrada",
            Presenca.valido == True,
        )
        .all()
    )

    eventos_em_andamento = []

    for entrada in entradas:
        saida = (
            db.query(Presenca)
            .filter(
                Presenca.id_evento == entrada.id_evento,
                Presenca.id_usuario == current_user.id_usuario,
                Presenca.tipo == "saida",
                Presenca.valido == True,
            )
            .first()
        )

        if saida:
            continue

        evento = (
            db.query(Evento)
            .filter(
                Evento.id_evento == entrada.id_evento,
                Evento.status == "ativo",
            )
            .first()
        )

        if evento:
            eventos_em_andamento.append(evento)
            
    return templates.TemplateResponse(
        request=request,
        name="aluno/index.html",
        context={
            "usuario": current_user,
            "projetos": projetos,
            "eventos_em_andamento": eventos_em_andamento,
            "salas": salas,
            "professores": professores,
        },
    )