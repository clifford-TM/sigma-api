from datetime import datetime
import json
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import (
    Evento,
    Dispositivo,
    RFIDTag,
    Usuario,
    Presenca,
    ComandoDispositivo,
    Sala,
    Turma,
    Curso,
    Materia,
    Professor,
    TurmaMateriaProfessor,
)

from app.schemas import TagAuthRequest, CadernoFinalPayload

router = APIRouter(prefix="/eventos", tags=["eventos"])
templates = Jinja2Templates(directory="public")


class ConfirmarComandoPayload(BaseModel):
    comando_id: int


def normalizar_uid(uid: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", uid).upper()


def obter_dispositivo_da_sala(db: Session, sala_id: int) -> Dispositivo | None:
    return (
        db.query(Dispositivo)
        .filter(
            Dispositivo.sala_id == sala_id,
            Dispositivo.ativo == True,
        )
        .first()
    )


def rota_lista_por_tipo(user_tipo: str) -> str:
    if user_tipo in ["professor", "aluno", "seguranca", "zelador", "tecnico", "admin"]:
        return "/eventos"
    return "/login"


def tipos_permitidos_para_usuario(user_tipo: str) -> list[str]:
    if user_tipo == "professor":
        return ["aula", "projeto"]
    if user_tipo == "aluno":
        return ["projeto"]
    if user_tipo == "seguranca":
        return ["inspecao"]
    if user_tipo == "tecnico":
        return ["manutencao"]
    if user_tipo == "zelador":
        return ["limpeza"]
    if user_tipo == "admin":
        return ["aula", "projeto", "inspecao", "manutencao", "limpeza"]
    return []

def template_form_por_tipo(tipo: str) -> str:
    if tipo == "aula":
        return "eventos/evento-aula.html"
    if tipo == "projeto":
        return "eventos/evento-projeto.html"
    if tipo in ["limpeza", "manutencao", "inspecao"]:
        return "eventos/evento-operacional.html"
    return "eventos/evento-form.html"


def carregar_alocacoes_professor(db: Session, current_user: Usuario) -> list[dict]:
    professor = (
        db.query(Professor)
        .filter(Professor.usuario_id == current_user.id_usuario)
        .first()
    )

    if not professor:
        return []

    alocacoes = (
        db.query(TurmaMateriaProfessor, Turma, Curso, Materia)
        .join(Turma, Turma.id_turma == TurmaMateriaProfessor.turma_id)
        .join(Curso, Curso.id_curso == Turma.curso_id)
        .join(Materia, Materia.id_materia == TurmaMateriaProfessor.materia_id)
        .filter(TurmaMateriaProfessor.professor_id == professor.id_professor)
        .all()
    )

    return [
        {
            "turma_id": turma.id_turma,
            "materia_id": materia.id_materia,
            "curso_codigo": curso.codigo,
            "curso_nome": curso.nome,
            "semestre": turma.semestre,
            "periodo": turma.periodo,
            "ano": turma.ano,
            "materia_codigo": materia.codigo,
            "materia_nome": materia.nome,
        }
        for _, turma, curso, materia in alocacoes
    ]

def template_lista_eventos() -> str:
    return "eventos/eventos-lista.html"


def template_form_evento() -> str:
    return "eventos/evento-form.html"


def template_editar_evento() -> str:
    return "eventos/evento-editar.html"


def template_cancelar_evento() -> str:
    return "eventos/evento-cancelar.html"


@router.get("")
def listar_eventos_usuario(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    eventos = (
        db.query(Evento)
        .filter(Evento.host == current_user.id_usuario)
        .order_by(Evento.inicio_previsto.desc())
        .all()
    )

    salas = {sala.id_sala: sala for sala in db.query(Sala).all()}
    professores = {
        professor.id_usuario: professor
        for professor in db.query(Usuario).filter(Usuario.tipo == "professor").all()
    }

    return templates.TemplateResponse(
        request=request,
        name=template_lista_eventos(),
        context={
            "usuario": current_user,
            "eventos": eventos,
            "projetos": eventos,
            "salas": salas,
            "professores": professores,
        },
    )


@router.get("/novo")
def formulario_novo_evento(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    salas = db.query(Sala).order_by(Sala.numero.asc()).all()
    tipos_permitidos = tipos_permitidos_para_usuario(current_user.tipo)

    tipo = request.query_params.get("tipo", "")

    if tipo not in tipos_permitidos:
        tipo = tipos_permitidos[0] if len(tipos_permitidos) == 1 else ""

    context = {
        "usuario": current_user,
        "erro": None,
        "valores": {"tipo": tipo},
        "salas": salas,
        "tipos_permitidos": tipos_permitidos,
    }

    if tipo == "aula":
        context["alocacoes"] = carregar_alocacoes_professor(db, current_user)

    if tipo == "projeto" and current_user.tipo == "aluno":
        professores = (
            db.query(Usuario)
            .filter(Usuario.tipo == "professor")
            .order_by(Usuario.nome.asc())
            .all()
        )
        context["professores"] = professores

    return templates.TemplateResponse(
        request=request,
        name=template_form_por_tipo(tipo),
        context=context,
    )

@router.post("")
def criar_evento(
    request: Request,
    tipo: str = Form(...),
    sala_id: int = Form(...),
    descricao: str = Form(""),
    inicio_previsto: str = Form(...),
    fim_previsto: str = Form(...),
    autorizado_por: int | None = Form(None),
    alocacao_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    descricao = descricao.strip()

    valores = {
        "sala_id": sala_id,
        "tipo": tipo,
        "descricao": descricao,
        "inicio_previsto": inicio_previsto,
        "fim_previsto": fim_previsto,
        "autorizado_por": autorizado_por,
        "alocacao_id": alocacao_id,
    }

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()
    tipos_permitidos = tipos_permitidos_para_usuario(current_user.tipo)

    context = {
        "usuario": current_user,
        "erro": None,
        "valores": valores,
        "salas": salas,
        "tipos_permitidos": tipos_permitidos,
    }

    if tipo == "aula":
        context["alocacoes"] = carregar_alocacoes_professor(db, current_user)

    if tipo == "projeto" and current_user.tipo == "aluno":
        context["professores"] = (
            db.query(Usuario)
            .filter(Usuario.tipo == "professor")
            .order_by(Usuario.nome.asc())
            .all()
        )

    if tipo not in tipos_permitidos:
        context["erro"] = "Tipo de evento inválido para este usuário."
        return templates.TemplateResponse(
            request=request,
            name=template_form_por_tipo(tipo),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    sala = db.query(Sala).filter(Sala.id_sala == sala_id).first()
    if not sala:
        context["erro"] = "A sala selecionada não existe."
        return templates.TemplateResponse(
            request=request,
            name=template_form_por_tipo(tipo),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if tipo == "projeto" and current_user.tipo == "aluno":
        professor = (
            db.query(Usuario)
            .filter(
                Usuario.id_usuario == autorizado_por,
                Usuario.tipo == "professor",
            )
            .first()
        )
        if not professor:
            context["erro"] = "O professor autorizador é inválido."
            return templates.TemplateResponse(
                request=request,
                name=template_form_por_tipo(tipo),
                context=context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    try:
        inicio_dt = datetime.fromisoformat(inicio_previsto)
        fim_dt = datetime.fromisoformat(fim_previsto)
    except ValueError:
        context["erro"] = "Data ou horário inválido."
        return templates.TemplateResponse(
            request=request,
            name=template_form_por_tipo(tipo),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if fim_dt <= inicio_dt:
        context["erro"] = "O horário de término deve ser posterior ao horário de início."
        return templates.TemplateResponse(
            request=request,
            name=template_form_por_tipo(tipo),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    turma_id = None
    materia_id = None

    if tipo == "aula":
        if current_user.tipo != "professor":
            context["erro"] = "Apenas professores podem criar aulas."
            return templates.TemplateResponse(
                request=request,
                name=template_form_por_tipo(tipo),
                context=context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            turma_id, materia_id = map(int, (alocacao_id or "").split(":"))
        except Exception:
            context["erro"] = "Selecione uma turma e matéria válidas."
            return templates.TemplateResponse(
                request=request,
                name=template_form_por_tipo(tipo),
                context=context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        professor = (
            db.query(Professor)
            .filter(Professor.usuario_id == current_user.id_usuario)
            .first()
        )

        alocacao = (
            db.query(TurmaMateriaProfessor)
            .filter(
                TurmaMateriaProfessor.turma_id == turma_id,
                TurmaMateriaProfessor.materia_id == materia_id,
                TurmaMateriaProfessor.professor_id == professor.id_professor,
            )
            .first()
            if professor
            else None
        )

        if not alocacao:
            context["erro"] = "Você não está vinculado a essa turma/matéria."
            return templates.TemplateResponse(
                request=request,
                name=template_form_por_tipo(tipo),
                context=context,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    conflito = (
        db.query(Evento)
        .filter(
            Evento.sala_id == sala_id,
            Evento.status.in_(["pendente_aprovacao", "agendado", "ativo", "pendente"]),
            Evento.inicio_previsto < fim_dt,
            Evento.fim_previsto > inicio_dt,
        )
        .first()
    )

    if conflito:
        context["erro"] = "Já existe um evento agendado nessa sala para esse horário."
        return templates.TemplateResponse(
            request=request,
            name=template_form_por_tipo(tipo),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    status_inicial = (
        "pendente_aprovacao"
        if tipo == "projeto" and current_user.tipo == "aluno"
        else "agendado"
    )

    novo_evento = Evento(
        tipo=tipo,
        host=current_user.id_usuario,
        autorizado_por=autorizado_por if tipo == "projeto" and current_user.tipo == "aluno" else None,
        forma_inicio="app",
        confirmado_por_rfid=False,
        sala_id=sala_id,
        turma_id=turma_id,
        materia_id=materia_id,
        status=status_inicial,
        descricao=descricao if descricao else None,
        inicio_previsto=inicio_dt,
        fim_previsto=fim_dt,
        inicio_real=None,
        fim_real=None,
    )

    db.add(novo_evento)
    db.commit()

    return RedirectResponse(
        url=rota_lista_por_tipo(current_user.tipo),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{evento_id}/editar")
def formulario_editar_evento(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
        )
        .first()
    )

    if not evento or evento.status not in ["agendado", "pendente_aprovacao"]:
        return RedirectResponse(
            url=rota_lista_por_tipo(current_user.tipo),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    valores = {
        "sala_id": evento.sala_id,
        "descricao": evento.descricao or "",
        "inicio_previsto": evento.inicio_previsto.strftime("%Y-%m-%dT%H:%M") if evento.inicio_previsto else "",
        "fim_previsto": evento.fim_previsto.strftime("%Y-%m-%dT%H:%M") if evento.fim_previsto else "",
        "autorizado_por": evento.autorizado_por,
    }

    context = {
        "usuario": current_user,
        "evento": evento,
        "erro": None,
        "valores": valores,
        "salas": salas,
    }

    if current_user.tipo == "aluno":
        professores = (
            db.query(Usuario)
            .filter(Usuario.tipo == "professor")
            .order_by(Usuario.nome.asc())
            .all()
        )
        context["professores"] = professores

    return templates.TemplateResponse(
        request=request,
        name=template_editar_evento(),
        context=context,
    )


@router.post("/{evento_id}/editar")
def atualizar_evento(
    evento_id: int,
    request: Request,
    sala_id: int = Form(...),
    descricao: str = Form(""),
    inicio_previsto: str = Form(...),
    fim_previsto: str = Form(...),
    autorizado_por: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
        )
        .first()
    )

    if not evento or evento.status not in ["agendado", "pendente_aprovacao"]:
        return RedirectResponse(
            url=rota_lista_por_tipo(current_user.tipo),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    descricao = descricao.strip()
    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    valores = {
        "sala_id": sala_id,
        "descricao": descricao,
        "inicio_previsto": inicio_previsto,
        "fim_previsto": fim_previsto,
        "autorizado_por": autorizado_por,
    }

    context = {
        "usuario": current_user,
        "evento": evento,
        "erro": None,
        "valores": valores,
        "salas": salas,
    }

    if current_user.tipo == "aluno":
        professores = (
            db.query(Usuario)
            .filter(Usuario.tipo == "professor")
            .order_by(Usuario.nome.asc())
            .all()
        )
        context["professores"] = professores

    sala = db.query(Sala).filter(Sala.id_sala == sala_id).first()
    if not sala:
        context["erro"] = "A sala selecionada não existe."
        return templates.TemplateResponse(
            request=request,
            name=template_editar_evento(),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        inicio_dt = datetime.fromisoformat(inicio_previsto)
        fim_dt = datetime.fromisoformat(fim_previsto)
    except ValueError:
        context["erro"] = "Data ou horário inválido."
        return templates.TemplateResponse(
            request=request,
            name=template_editar_evento(),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if fim_dt <= inicio_dt:
        context["erro"] = "O horário de término deve ser posterior ao horário de início."
        return templates.TemplateResponse(
            request=request,
            name=template_editar_evento(),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    conflito = (
        db.query(Evento)
        .filter(
            Evento.id_evento != evento.id_evento,
            Evento.sala_id == sala_id,
            Evento.status.in_(["pendente_aprovacao", "agendado", "ativo", "pendente"]),
            Evento.inicio_previsto < fim_dt,
            Evento.fim_previsto > inicio_dt,
        )
        .first()
    )

    if conflito:
        context["erro"] = "Já existe um evento agendado nessa sala para esse horário."
        return templates.TemplateResponse(
            request=request,
            name=template_editar_evento(),
            context=context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    evento.sala_id = sala_id
    evento.descricao = descricao if descricao else None
    evento.inicio_previsto = inicio_dt
    evento.fim_previsto = fim_dt

    if evento.tipo == "projeto":
        evento.autorizado_por = autorizado_por

    db.commit()

    return RedirectResponse(
        url=rota_lista_por_tipo(current_user.tipo),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{evento_id}/cancelar")
def formulario_cancelar_evento(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
        )
        .first()
    )

    if not evento or evento.status not in ["agendado", "pendente_aprovacao"]:
        return RedirectResponse(
            url=rota_lista_por_tipo(current_user.tipo),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request=request,
        name=template_cancelar_evento(),
        context={
            "usuario": current_user,
            "evento": evento,
            "erro": None,
        },
    )


@router.post("/{evento_id}/cancelar")
def cancelar_evento(
    evento_id: int,
    request: Request,
    motivo: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
        )
        .first()
    )

    if not evento or evento.status not in ["agendado", "pendente_aprovacao"]:
        return RedirectResponse(
            url=rota_lista_por_tipo(current_user.tipo),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    motivo = motivo.strip()

    if not motivo:
        return templates.TemplateResponse(
            request=request,
            name=template_cancelar_evento(),
            context={
                "usuario": current_user,
                "evento": evento,
                "erro": "Informe uma justificativa para cancelar o evento.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    evento.status = "cancelado"
    evento.motivo_nao_realizacao = motivo

    comandos_pendentes = (
        db.query(ComandoDispositivo)
        .filter(
            ComandoDispositivo.status == "pendente",
            ComandoDispositivo.payload_json.contains(
                f'"evento_id":{evento.id_evento}'
            ),
        )
        .all()
    )

    if not comandos_pendentes:
        comandos_pendentes = (
            db.query(ComandoDispositivo)
            .filter(
                ComandoDispositivo.status == "pendente",
                ComandoDispositivo.payload_json.contains(
                    f'"evento_id": {evento.id_evento}'
                ),
            )
            .all()
        )

    for comando in comandos_pendentes:
        comando.status = "cancelado"
        comando.consumido_em = datetime.utcnow()

    db.commit()

    return RedirectResponse(
        url=rota_lista_por_tipo(current_user.tipo),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{evento_id}/iniciar")
def iniciar_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
            Evento.status == "agendado",
        )
        .first()
    )

    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado ou não pode ser iniciado.")

    dispositivo = obter_dispositivo_da_sala(db, evento.sala_id)
    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo da sala não encontrado.")

    comando = ComandoDispositivo(
        device_id=dispositivo.identificador_fisico,
        acao="iniciar_evento",
        payload_json=json.dumps({
            "evento_id": evento.id_evento,
            "sala_id": evento.sala_id,
            "host_id": current_user.id_usuario,
            "host_nome": current_user.nome,
            "tipo": evento.tipo,
        }),
        status="pendente",
    )

    evento.status = "pendente"
    db.add(comando)
    db.commit()

    return RedirectResponse(
        url=rota_lista_por_tipo(current_user.tipo),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{evento_id}/disparar-fim")
def disparar_encerramento_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.host == current_user.id_usuario,
            Evento.status == "ativo",
        )
        .first()
    )

    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado ou não pode ser encerrado.")

    dispositivo = obter_dispositivo_da_sala(db, evento.sala_id)
    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo da sala não encontrado.")

    comando = ComandoDispositivo(
        device_id=dispositivo.identificador_fisico,
        acao="encerrar_evento",
        payload_json=json.dumps({
            "evento_id": evento.id_evento,
            "sala_id": evento.sala_id,
            "host_id": evento.host,
            "tipo": evento.tipo,
            "host_nome": current_user.nome,
        }),
        status="pendente",
    )

    evento.status = "encerrando"
    db.add(comando)
    db.commit()

    return {"ok": True, "mensagem": "Comando registrado para o dispositivo."}


@router.post("/{evento_id}/autorizar-inicio")
def autorizar_inicio(
    evento_id: int,
    payload: TagAuthRequest,
    db: Session = Depends(get_db),
):
    uid = normalizar_uid(payload.uid)

    tag = (
        db.query(RFIDTag)
        .filter(
            RFIDTag.codigo == uid,
            RFIDTag.ativa == True,
        )
        .first()
    )

    if not tag:
        raise HTTPException(status_code=404, detail="Tag não encontrada")

    evento = db.query(Evento).filter(Evento.id_evento == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    if tag.usuario_id != evento.host:
        raise HTTPException(status_code=403, detail="Tag não pertence ao responsável pelo evento")

    evento.status = "ativo"
    evento.confirmado_por_rfid = True
    evento.forma_inicio = "app"
    evento.inicio_real = datetime.utcnow()

    db.commit()

    return {"ok": True, "mensagem": "Evento iniciado com sucesso"}


@router.post("/{evento_id}/autorizar-fim")
def autorizar_fim_evento(
    evento_id: int,
    payload: TagAuthRequest,
    db: Session = Depends(get_db),
):
    uid = normalizar_uid(payload.uid)

    evento = db.query(Evento).filter(Evento.id_evento == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    tag = (
        db.query(RFIDTag)
        .filter(
            RFIDTag.codigo == uid,
            RFIDTag.ativa == True,
        )
        .first()
    )

    if not tag:
        raise HTTPException(status_code=403, detail="Tag não cadastrada.")

    usuario = db.query(Usuario).filter(Usuario.id_usuario == tag.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=403, detail="Usuário da tag não encontrado.")

    if usuario.id_usuario != evento.host:
        raise HTTPException(status_code=403, detail="Usuário não autorizado para encerrar o evento.")

    evento.status = "encerrando"
    db.commit()

    return {
        "ok": True,
        "mensagem": "Encerramento autorizado.",
        "usuario_id": usuario.id_usuario,
        "usuario_nome": usuario.nome,
        "evento_id": evento.id_evento,
    }


@router.post("/caderno-final")
def receber_caderno_final(
    payload: CadernoFinalPayload,
    db: Session = Depends(get_db),
):
    evento = db.query(Evento).filter(Evento.id_evento == payload.evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    inseridas = 0

    for participante in payload.participantes:
        uid = normalizar_uid(participante.uid)

        tag = (
            db.query(RFIDTag)
            .filter(
                RFIDTag.codigo == uid,
                RFIDTag.ativa == True,
            )
            .first()
        )

        if not tag:
            continue

        presenca = Presenca(
            id_evento=payload.evento_id,
            id_usuario=tag.usuario_id,
            data_hora=datetime.now(),
            tipo="entrada",
            origem="rfid",
        )

        db.add(presenca)
        inseridas += 1

    evento.status = "finalizado"
    if not evento.fim_real:
        evento.fim_real = datetime.now()

    db.commit()

    return {
        "ok": True,
        "mensagem": "Caderno final recebido.",
        "evento_id": payload.evento_id,
        "presencas_inseridas": inseridas,
    }


@router.get("/dispositivos/{device_id}/comando-pendente")
def obter_comando_pendente(device_id: str, db: Session = Depends(get_db)):
    comando = (
        db.query(ComandoDispositivo)
        .filter(
            ComandoDispositivo.device_id == device_id,
            ComandoDispositivo.status == "pendente",
        )
        .order_by(ComandoDispositivo.criado_em.asc())
        .first()
    )

    if not comando:
        return {"acao": None}

    return {
        "comando_id": comando.id_comando,
        "acao": comando.acao,
        "payload": json.loads(comando.payload_json or "{}"),
    }


@router.post("/dispositivos/{device_id}/confirmar-comando")
def confirmar_comando(
    device_id: str,
    payload: ConfirmarComandoPayload,
    db: Session = Depends(get_db),
):
    comando = (
        db.query(ComandoDispositivo)
        .filter(
            ComandoDispositivo.id_comando == payload.comando_id,
            ComandoDispositivo.device_id == device_id,
        )
        .first()
    )

    if not comando:
        raise HTTPException(status_code=404, detail="Comando não encontrado")

    comando.status = "consumido"
    comando.consumido_em = datetime.utcnow()
    db.commit()

    return {"ok": True}