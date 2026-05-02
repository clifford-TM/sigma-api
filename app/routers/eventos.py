from datetime import datetime, timedelta
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
    EventoRelacao
)

from app.schemas import TagAuthRequest, CadernoFinalPayload

router = APIRouter(prefix="/eventos", tags=["eventos"])
templates = Jinja2Templates(directory="public")

TOLERANCIA_INICIO = timedelta(minutes=15)
TOLERANCIA_FIM = timedelta(minutes=15)


def agora() -> datetime:
    # Mantém o padrão atual do projeto: datas naive/local.
    return datetime.now()


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


def pode_iniciar_evento(evento: Evento) -> tuple[bool, str]:
    now = agora()

    inicio_minimo = evento.inicio_previsto - TOLERANCIA_INICIO
    inicio_maximo = evento.inicio_previsto + TOLERANCIA_INICIO

    if now < inicio_minimo:
        return False, "Ainda está muito cedo para iniciar este evento."

    if now > inicio_maximo:
        return False, "Este evento ultrapassou a janela de início e será marcado como não realizado."

    return True, ""


def deve_marcar_nao_realizado(evento: Evento) -> bool:
    return (
        evento.status in ["agendado", "pendente"]
        and agora() > evento.inicio_previsto + TOLERANCIA_INICIO
    )


def deve_encerrar_automaticamente(evento: Evento) -> bool:
    return (
        evento.status == "ativo"
        and agora() > evento.fim_previsto + TOLERANCIA_FIM
    )


def buscar_comandos_pendentes_do_evento(
    db: Session,
    evento_id: int,
) -> list[ComandoDispositivo]:
    comandos = (
        db.query(ComandoDispositivo)
        .filter(
            ComandoDispositivo.status == "pendente",
            ComandoDispositivo.payload_json.contains(f'"evento_id":{evento_id}'),
        )
        .all()
    )

    if comandos:
        return comandos

    return (
        db.query(ComandoDispositivo)
        .filter(
            ComandoDispositivo.status == "pendente",
            ComandoDispositivo.payload_json.contains(f'"evento_id": {evento_id}'),
        )
        .all()
    )


def cancelar_comandos_pendentes_do_evento(db: Session, evento_id: int) -> int:
    comandos = buscar_comandos_pendentes_do_evento(db, evento_id)
    cancelados = 0

    for comando in comandos:
        comando.status = "cancelado"
        comando.consumido_em = agora()
        cancelados += 1

    return cancelados


def registrar_saidas_automaticas(
    db: Session,
    evento: Evento,
    data_saida: datetime,
) -> int:
    entradas = (
        db.query(Presenca)
        .filter(
            Presenca.id_evento == evento.id_evento,
            Presenca.tipo == "entrada",
            Presenca.valido == True,
        )
        .all()
    )

    saidas_inseridas = 0

    for entrada in entradas:
        saida_existente = (
            db.query(Presenca)
            .filter(
                Presenca.id_evento == evento.id_evento,
                Presenca.id_usuario == entrada.id_usuario,
                Presenca.tipo == "saida",
                Presenca.valido == True,
            )
            .first()
        )

        if saida_existente:
            continue

        saida = Presenca(
            id_evento=evento.id_evento,
            id_usuario=entrada.id_usuario,
            dispositivo_id=entrada.dispositivo_id,
            data_hora=data_saida,
            tipo="saida",
            origem="sincronizacao_dispositivo",
        )

        db.add(saida)
        saidas_inseridas += 1

    return saidas_inseridas


def criar_comando_encerramento_evento(
    db: Session,
    evento: Evento,
    modo: str = "manual",
    host_nome: str | None = None,
    motivo: str | None = None,
) -> bool:
    dispositivo = obter_dispositivo_da_sala(db, evento.sala_id)

    if not dispositivo:
        return False

    comando_existente = (
        db.query(ComandoDispositivo)
        .filter(
            ComandoDispositivo.device_id == dispositivo.identificador_fisico,
            ComandoDispositivo.acao == "encerrar_evento",
            ComandoDispositivo.status == "pendente",
            ComandoDispositivo.payload_json.contains(f"\"evento_id\": {evento.id_evento}"),
        )
        .first()
    )

    if not comando_existente:
        comando_existente = (
            db.query(ComandoDispositivo)
            .filter(
                ComandoDispositivo.device_id == dispositivo.identificador_fisico,
                ComandoDispositivo.acao == "encerrar_evento",
                ComandoDispositivo.status == "pendente",
                ComandoDispositivo.payload_json.contains(f"\"evento_id\":{evento.id_evento}"),
            )
            .first()
        )

    if comando_existente:
        return False

    comando = ComandoDispositivo(
        device_id=dispositivo.identificador_fisico,
        acao="encerrar_evento",
        payload_json=json.dumps({
            "evento_id": evento.id_evento,
            "sala_id": evento.sala_id,
            "host_id": evento.host,
            "tipo": evento.tipo,
            "host_nome": host_nome or "Encerramento automático",
            "modo": modo,
            "motivo": motivo,
        }),
        status="pendente",
    )

    db.add(comando)
    return True


def sincronizar_eventos(db: Session) -> dict:
    eventos = (
        db.query(Evento)
        .filter(Evento.status.in_(["agendado", "pendente", "ativo", "encerrando"]))
        .all()
    )

    now = agora()
    nao_realizados = 0
    encerramentos_solicitados = 0
    comandos_encerramento_criados = 0
    comandos_cancelados_total = 0

    for evento in eventos:
        if deve_marcar_nao_realizado(evento):
            evento.status = "nao_realizado"
            evento.motivo_nao_realizacao = (
                "Evento não iniciado dentro da janela de tolerância de 15 minutos."
            )
            comandos_cancelados_total += cancelar_comandos_pendentes_do_evento(
                db=db,
                evento_id=evento.id_evento,
            )
            nao_realizados += 1
            continue

        if deve_encerrar_automaticamente(evento):
            comando_criado = criar_comando_encerramento_evento(
                db=db,
                evento=evento,
                modo="automatico",
                host_nome="Encerramento automático",
                motivo="Evento ultrapassou o horário previsto de encerramento.",
            )

            evento.status = "encerrando"
            encerramentos_solicitados += 1

            if comando_criado:
                comandos_encerramento_criados += 1

    if nao_realizados or encerramentos_solicitados or comandos_encerramento_criados or comandos_cancelados_total:
        db.commit()

    return {
        "nao_realizados": nao_realizados,
        "encerramentos_solicitados": encerramentos_solicitados,
        "comandos_encerramento_criados": comandos_encerramento_criados,
        "comandos_cancelados": comandos_cancelados_total,
    }

def usuario_pode_operar_evento(usuario: Usuario, evento: Evento) -> bool:
    return evento.host == usuario.id_usuario or usuario.tipo == "seguranca"

@router.get("")
def listar_eventos_usuario(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    sincronizar_eventos(db)

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

    if inicio_dt < agora():
        context["erro"] = "Não é possível criar eventos em datas ou horários que já passaram."
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

    if inicio_dt < agora():
        context["erro"] = "Não é possível editar o evento para datas ou horários que já passaram."
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
        comando.consumido_em = agora()

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
    sincronizar_eventos(db)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.status == "agendado",
        )
        .first()
    )

    if not evento or not usuario_pode_operar_evento(current_user, evento):
        raise HTTPException(status_code=404, detail="Evento não encontrado ou não pode ser iniciado.")

    pode_iniciar, mensagem = pode_iniciar_evento(evento)
    if not pode_iniciar:
        if deve_marcar_nao_realizado(evento):
            evento.status = "nao_realizado"
            evento.motivo_nao_realizacao = "Evento não iniciado dentro da janela de tolerância de 15 minutos."
            cancelar_comandos_pendentes_do_evento(db, evento.id_evento)
            db.commit()
        raise HTTPException(status_code=400, detail=mensagem)

    dispositivo = obter_dispositivo_da_sala(db, evento.sala_id)
    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo da sala não encontrado.")

    modo = "manual" if evento.host == current_user.id_usuario else "contingencia"

    comando = ComandoDispositivo(
        device_id=dispositivo.identificador_fisico,
        acao="iniciar_evento",
        payload_json=json.dumps({
            "evento_id": evento.id_evento,
            "sala_id": evento.sala_id,
            "host_id": evento.host,
            "tipo": evento.tipo,
            "modo": modo,
            "acionado_por_id": current_user.id_usuario,
            "acionado_por_nome": current_user.nome,
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
    sincronizar_eventos(db)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            Evento.status == "ativo",
        )
        .first()
    )

    if not evento or not usuario_pode_operar_evento(current_user, evento):
        raise HTTPException(status_code=404, detail="Evento não encontrado ou não pode ser encerrado.")

    dispositivo = obter_dispositivo_da_sala(db, evento.sala_id)
    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo da sala não encontrado.")

    modo = "manual" if evento.host == current_user.id_usuario else "contingencia"

    comando = ComandoDispositivo(
        device_id=dispositivo.identificador_fisico,
        acao="encerrar_evento",
        payload_json=json.dumps({
            "evento_id": evento.id_evento,
            "sala_id": evento.sala_id,
            "host_id": evento.host,
            "tipo": evento.tipo,
            "host_nome": current_user.nome,
            "modo": modo,
            "acionado_por_id": current_user.id_usuario,
            "acionado_por_nome": current_user.nome,
            "motivo": (
                "Encerramento solicitado pelo responsável."
                if modo == "manual"
                else "Encerramento de contingência solicitado pela segurança."
            ),
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
    sincronizar_eventos(db)

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

    if evento.status not in ["agendado", "pendente"]:
        raise HTTPException(status_code=400, detail="Evento não está aguardando início.")

    pode_iniciar, mensagem = pode_iniciar_evento(evento)
    if not pode_iniciar:
        if deve_marcar_nao_realizado(evento):
            evento.status = "nao_realizado"
            evento.motivo_nao_realizacao = "Evento não iniciado dentro da janela de tolerância de 15 minutos."
            cancelar_comandos_pendentes_do_evento(db, evento.id_evento)
            db.commit()
        raise HTTPException(status_code=400, detail=mensagem)

    if tag.usuario_id != evento.host:
        raise HTTPException(status_code=403, detail="Tag não pertence ao responsável pelo evento")

    evento.status = "ativo"
    evento.confirmado_por_rfid = True
    evento.forma_inicio = "app"
    evento.inicio_real = agora()

    db.commit()

    return {"ok": True, "mensagem": "Evento iniciado com sucesso"}


@router.post("/{evento_id}/autorizar-fim")
def autorizar_fim_evento(
    evento_id: int,
    payload: TagAuthRequest,
    db: Session = Depends(get_db),
):
    sincronizar_eventos(db)

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

@router.post("/{evento_id}/autorizar-contingencia")
def autorizar_contingencia_evento(
    evento_id: int,
    payload: TagAuthRequest,
    db: Session = Depends(get_db),
):
    sincronizar_eventos(db)

    uid = normalizar_uid(payload.uid)

    evento = db.query(Evento).filter(Evento.id_evento == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    if evento.status not in ["ativo", "encerrando"]:
        raise HTTPException(
            status_code=400,
            detail="Evento não está em estado válido para contingência.",
        )

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

    if usuario.tipo != "seguranca":
        raise HTTPException(
            status_code=403,
            detail="Tag não pertence a um usuário de segurança.",
        )

    evento.status = "encerrando"
    db.commit()

    return {
        "ok": True,
        "mensagem": "Encerramento de contingência autorizado.",
        "usuario_id": usuario.id_usuario,
        "usuario_nome": usuario.nome,
        "evento_id": evento.id_evento,
    }

@router.post("/{evento_id}/registrar-ponto")
def registrar_ponto_evento(
    evento_id: int,
    payload: TagAuthRequest,
    db: Session = Depends(get_db),
):
    sincronizar_eventos(db)

    evento = db.query(Evento).filter(Evento.id_evento == evento_id).first()

    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    if evento.status != "ativo":
        raise HTTPException(status_code=400, detail="Evento não está ativo.")

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
        raise HTTPException(status_code=403, detail="Tag RFID não cadastrada ou inativa.")

    usuario = db.query(Usuario).filter(Usuario.id_usuario == tag.usuario_id).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário da tag não encontrado.")

    dispositivo = (
        db.query(Dispositivo)
        .filter(Dispositivo.identificador_fisico == payload.device_id)
        .first()
    )

    entrada = (
        db.query(Presenca)
        .filter(
            Presenca.id_evento == evento.id_evento,
            Presenca.id_usuario == usuario.id_usuario,
            Presenca.tipo == "entrada",
            Presenca.valido == True,
        )
        .first()
    )

    saida = (
        db.query(Presenca)
        .filter(
            Presenca.id_evento == evento.id_evento,
            Presenca.id_usuario == usuario.id_usuario,
            Presenca.tipo == "saida",
            Presenca.valido == True,
        )
        .first()
    )

    if not entrada:
        tipo_registro = "entrada"
        mensagem = "Entrada registrada com sucesso."
    elif not saida:
        tipo_registro = "saida"
        mensagem = "Saída registrada com sucesso."
    else:
        return {
            "ok": False,
            "mensagem": "Usuário já possui entrada e saída registradas neste evento.",
            "evento_id": evento.id_evento,
            "usuario_id": usuario.id_usuario,
            "usuario_nome": usuario.nome,
        }

    presenca = Presenca(
        id_evento=evento.id_evento,
        id_usuario=usuario.id_usuario,
        dispositivo_id=dispositivo.id_dispositivo if dispositivo else None,
        data_hora=agora(),
        tipo=tipo_registro,
        origem="rfid",
    )

    db.add(presenca)
    db.commit()

    return {
        "ok": True,
        "mensagem": mensagem,
        "evento_id": evento.id_evento,
        "usuario_id": usuario.id_usuario,
        "usuario_nome": usuario.nome,
        "tipo": tipo_registro,
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
    ignoradas = 0

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
            ignoradas += 1
            continue

        tipo_presenca = getattr(participante, "tipo", "entrada")

        presenca_existente = (
            db.query(Presenca)
            .filter(
                Presenca.id_evento == payload.evento_id,
                Presenca.id_usuario == tag.usuario_id,
                Presenca.tipo == tipo_presenca,
                Presenca.valido == True,
            )
            .first()
        )

        if presenca_existente:
            ignoradas += 1
            continue

        presenca = Presenca(
            id_evento=payload.evento_id,
            id_usuario=tag.usuario_id,
            data_hora=participante.timestamp,
            tipo=tipo_presenca,
            origem="rfid",
        )

        db.add(presenca)
        inseridas += 1

    db.flush()

    # 🔥 FINALIZA EVENTO
    evento.status = "finalizado"

    # 🔥 INSPEÇÃO AUTOMÁTICA PARA PROJETOS
    if evento.tipo == "projeto":
        inicio_inspecao = agora() + timedelta(minutes=1)
        fim_inspecao = inicio_inspecao + timedelta(minutes=30)

        # busca um segurança padrão
        seguranca_padrao = (
            db.query(Usuario)
            .filter(Usuario.tipo == "seguranca")
            .order_by(Usuario.id_usuario.asc())
            .first()
        )

        host_inspecao = (
            seguranca_padrao.id_usuario
            if seguranca_padrao
            else evento.host
        )

        nova_inspecao = Evento(
            tipo="inspecao",
            host=host_inspecao,
            sala_id=evento.sala_id,
            status="agendado",
            descricao=f"Inspeção automática do projeto #{evento.id_evento}",
            inicio_previsto=inicio_inspecao,
            fim_previsto=fim_inspecao,
            forma_inicio="app",
            confirmado_por_rfid=False,
        )

        db.add(nova_inspecao)
        db.flush()  # 🔥 pega id_evento da inspeção

        # 🔥 RELAÇÃO PROJETO → INSPEÇÃO
        relacao = EventoRelacao(
            evento_origem_id=evento.id_evento,
            evento_destino_id=nova_inspecao.id_evento,
            tipo_relacao="validacao_pos_projeto",
        )

        db.add(relacao)

    # 🔥 GARANTE FIM REAL
    if not evento.fim_real:
        evento.fim_real = agora()

    # 🔥 SAÍDAS AUTOMÁTICAS
    saidas_inseridas = registrar_saidas_automaticas(
        db=db,
        evento=evento,
        data_saida=evento.fim_real,
    )

    db.commit()

    return {
        "ok": True,
        "mensagem": "Caderno final recebido.",
        "evento_id": payload.evento_id,
        "presencas_inseridas": inseridas,
        "presencas_ignoradas": ignoradas,
        "saidas_inseridas": saidas_inseridas,
    }

@router.get("/dispositivos/{device_id}/comando-pendente")
def obter_comando_pendente(device_id: str, db: Session = Depends(get_db)):
    sincronizar_eventos(db)

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
    comando.consumido_em = agora()
    db.commit()

    return {"ok": True}