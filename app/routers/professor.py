from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Evento, Sala, Usuario

router = APIRouter(prefix="/professor", tags=["professor"])
templates = Jinja2Templates(directory="public")


def professor_autenticado(current_user: Usuario) -> bool:
    return current_user.tipo == "professor"


@router.get("/dashboard")
def dashboard_professor(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    proximos_eventos = (
        db.query(Evento)
        .filter(
            Evento.host == current_user.id_usuario,
            Evento.status.in_(["agendado", "pendente"]),
        )
        .order_by(Evento.inicio_previsto.asc())
        .limit(5)
        .all()
    )

    eventos_em_andamento = (
        db.query(Evento)
        .filter(
            Evento.host == current_user.id_usuario,
            Evento.status.in_(["ativo", "encerrando", "aguardando_validacao"]),
        )
        .order_by(Evento.inicio_previsto.asc())
        .limit(5)
        .all()
    )

    projetos_pendentes = (
        db.query(Evento)
        .filter(
            Evento.tipo == "projeto",
            Evento.autorizado_por == current_user.id_usuario,
            Evento.status == "pendente",
        )
        .order_by(Evento.inicio_previsto.asc())
        .limit(5)
        .all()
    )

    salas = {
        sala.id_sala: sala
        for sala in db.query(Sala).all()
    }

    return templates.TemplateResponse(
        request=request,
        name="professor/index.html",
        context={
            "usuario": current_user,
            "proximos_eventos": proximos_eventos,
            "eventos_em_andamento": eventos_em_andamento,
            "projetos_pendentes": projetos_pendentes,
            "salas": salas,
            "agora": datetime.now(),
        },
    )


@router.get("/eventos")
def listar_eventos_professor(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    eventos = (
        db.query(Evento)
        .filter(Evento.host == current_user.id_usuario)
        .order_by(Evento.inicio_previsto.desc())
        .all()
    )

    salas = {
        sala.id_sala: sala
        for sala in db.query(Sala).all()
    }

    return templates.TemplateResponse(
        request=request,
        name="professor/eventos-lista.html",
        context={
            "usuario": current_user,
            "eventos": eventos,
            "salas": salas,
        },
    )


@router.get("/eventos/novo")
def formulario_novo_evento(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    salas = (
        db.query(Sala)
        .order_by(Sala.numero.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="professor/evento-form.html",
        context={
            "usuario": current_user,
            "erro": None,
            "valores": {},
            "salas": salas,
        },
    )


@router.post("/eventos")
def criar_evento_professor(
    request: Request,
    tipo: str = Form(...),
    sala_id: int = Form(...),
    descricao: str = Form(""),
    inicio_previsto: str = Form(...),
    fim_previsto: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    descricao = descricao.strip()

    valores = {
        "sala_id": sala_id,
        "tipo": tipo,
        "descricao": descricao,
        "inicio_previsto": inicio_previsto,
        "fim_previsto": fim_previsto,
    }

    salas = (
        db.query(Sala)
        .order_by(Sala.numero.asc())
        .all()
    )

    sala = (
        db.query(Sala)
        .filter(Sala.id_sala == sala_id)
        .first()
    )

    if not sala:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-form.html",
            context={
                "usuario": current_user,
                "erro": "A sala selecionada não existe.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if tipo not in ["aula", "projeto"]:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-form.html",
            context={
                "usuario": current_user,
                "erro": "Tipo de evento inválido.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    
    # caso seja projeto
    autorizado_por = (
    current_user.id_usuario
    if tipo == "projeto"
    else None
)
    try:
        inicio_dt = datetime.fromisoformat(inicio_previsto)
        fim_dt = datetime.fromisoformat(fim_previsto)
    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-form.html",
            context={
                "usuario": current_user,
                "erro": "Data ou horário inválido.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if fim_dt <= inicio_dt:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-form.html",
            context={
                "usuario": current_user,
                "erro": "O horário de término deve ser posterior ao horário de início.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    conflito = (
        db.query(Evento)
        .filter(
            Evento.sala_id == sala_id,
            Evento.status.in_(["agendado", "ativo", "pendente"]),
            Evento.inicio_previsto < fim_dt,
            Evento.fim_previsto > inicio_dt,
        )
        .first()
    )

    if conflito:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-form.html",
            context={
                "usuario": current_user,
                "erro": "Já existe um evento agendado nessa sala para esse horário.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    novo_evento = Evento(
        tipo=tipo,
        host=current_user.id_usuario,
        autorizado_por=autorizado_por,
        forma_inicio="app",
        confirmado_por_rfid=False,
        sala_id=sala_id,
        status="agendado",
        descricao=descricao if descricao else None,
        inicio_previsto=inicio_dt,
        fim_previsto=fim_dt,
    )

    db.add(novo_evento)
    db.commit()

    return RedirectResponse(
        url="/professor/eventos",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.get("/eventos/{evento_id}/editar")
def formulario_editar_evento(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
        )
        .first()
    )

    if not evento:
        return RedirectResponse(url="/professor/eventos", status_code=status.HTTP_303_SEE_OTHER)

    if evento.status not in ["agendado", "pendente"]:
        return RedirectResponse(url="/professor/eventos", status_code=status.HTTP_303_SEE_OTHER)

    salas = (
        db.query(Sala)
        .order_by(Sala.numero.asc())
        .all()
    )

    valores = {
        "sala_id": evento.sala_id,
        "descricao": evento.descricao or "",
        "inicio_previsto": evento.inicio_previsto.strftime("%Y-%m-%dT%H:%M") if evento.inicio_previsto else "",
        "fim_previsto": evento.fim_previsto.strftime("%Y-%m-%dT%H:%M") if evento.fim_previsto else "",
    }

    return templates.TemplateResponse(
        request=request,
        name="professor/evento-editar.html",
        context={
            "usuario": current_user,
            "evento": evento,
            "erro": None,
            "valores": valores,
            "salas": salas,
        },
    )

@router.post("/eventos/{evento_id}/editar")
def atualizar_evento_professor(
    evento_id: int,
    request: Request,
    sala_id: int = Form(...),
    descricao: str = Form(""),
    inicio_previsto: str = Form(...),
    fim_previsto: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
        )
        .first()
    )

    if not evento:
        return RedirectResponse(url="/professor/eventos", status_code=status.HTTP_303_SEE_OTHER)

    if evento.status not in ["agendado", "pendente"]:
        return RedirectResponse(url="/professor/eventos", status_code=status.HTTP_303_SEE_OTHER)

    descricao = descricao.strip()

    valores = {
        "sala_id": sala_id,
        "descricao": descricao,
        "inicio_previsto": inicio_previsto,
        "fim_previsto": fim_previsto,
    }

    salas = (
        db.query(Sala)
        .order_by(Sala.numero.asc())
        .all()
    )

    sala = db.query(Sala).filter(Sala.id_sala == sala_id).first()
    if not sala:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-editar.html",
            context={
                "usuario": current_user,
                "evento": evento,
                "erro": "A sala selecionada não existe.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        inicio_dt = datetime.fromisoformat(inicio_previsto)
        fim_dt = datetime.fromisoformat(fim_previsto)
    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-editar.html",
            context={
                "usuario": current_user,
                "evento": evento,
                "erro": "Data ou horário inválido.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if fim_dt <= inicio_dt:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-editar.html",
            context={
                "usuario": current_user,
                "evento": evento,
                "erro": "O horário de término deve ser posterior ao horário de início.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    conflito = (
        db.query(Evento)
        .filter(
            Evento.id_evento != evento.id_evento,
            Evento.sala_id == sala_id,
            Evento.status.in_(["agendado", "ativo", "pendente"]),
            Evento.inicio_previsto < fim_dt,
            Evento.fim_previsto > inicio_dt,
        )
        .first()
    )

    if conflito:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-editar.html",
            context={
                "usuario": current_user,
                "evento": evento,
                "erro": "Já existe um evento agendado nessa sala para esse horário.",
                "valores": valores,
                "salas": salas,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    evento.sala_id = sala_id
    evento.descricao = descricao if descricao else None
    evento.inicio_previsto = inicio_dt
    evento.fim_previsto = fim_dt

    db.commit()

    return RedirectResponse(
        url="/professor/eventos",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.get("/eventos/{evento_id}/cancelar")
def formulario_cancelar_evento(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
        )
        .first()
    )

    if not evento or evento.status not in ["agendado", "pendente"]:
        return RedirectResponse(
            url="/professor/eventos",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request=request,
        name="professor/evento-cancelar.html",
        context={
            "usuario": current_user,
            "evento": evento,
            "erro": None,
        },
    )

@router.post("/eventos/{evento_id}/cancelar")
def cancelar_evento(
    evento_id: int,
    request: Request,
    motivo: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
        )
        .first()
    )

    if not evento or evento.status not in ["agendado", "pendente"]:
        return RedirectResponse(
            url="/professor/eventos",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    motivo = motivo.strip()

    if not motivo:
        return templates.TemplateResponse(
            request=request,
            name="professor/evento-cancelar.html",
            context={
                "usuario": current_user,
                "evento": evento,
                "erro": "Informe uma justificativa para cancelar o evento.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    evento.status = "cancelado"
    evento.motivo_nao_realizacao = motivo

    db.commit()

    return RedirectResponse(
        url="/professor/eventos",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.get("/projetos/{evento_id}/aprovar")
def aprovar_projeto(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.tipo == "projeto",
            Evento.autorizado_por == current_user.id_usuario,
            Evento.status == "pendente",
        )
        .first()
    )

    if not evento:
        return RedirectResponse(url="/professor/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    evento.status = "agendado"
    db.commit()

    return RedirectResponse(url="/professor/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/projetos/{evento_id}/reprovar")
def formulario_reprovar_projeto(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.tipo == "projeto",
            Evento.autorizado_por == current_user.id_usuario,
            Evento.status == "pendente",
        )
        .first()
    )

    if not evento:
        return RedirectResponse(url="/professor/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="professor/projeto-reprovar.html",
        context={
            "usuario": current_user,
            "evento": evento,
            "erro": None,
        },
    )

@router.post("/projetos/{evento_id}/reprovar")
def reprovar_projeto(
    evento_id: int,
    request: Request,
    motivo: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not professor_autenticado(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.tipo == "projeto",
            Evento.autorizado_por == current_user.id_usuario,
            Evento.status == "pendente",
        )
        .first()
    )

    if not evento:
        return RedirectResponse(url="/professor/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    motivo = motivo.strip()

    if not motivo:
        return templates.TemplateResponse(
            request=request,
            name="professor/projeto-reprovar.html",
            context={
                "usuario": current_user,
                "evento": evento,
                "erro": "Informe uma justificativa para reprovar o projeto.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    evento.status = "cancelado"
    evento.motivo_nao_realizacao = motivo
    db.commit()

    return RedirectResponse(url="/professor/dashboard", status_code=status.HTTP_303_SEE_OTHER)