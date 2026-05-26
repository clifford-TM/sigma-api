# app/routers/seguranca.py

from datetime import datetime

from fastapi import (APIRouter, Depends, Request, 
                     status, HTTPException, Form)
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.deps import get_current_user
from app.models import (Evento, Sala, Usuario, EventoRelacao, 
                        EstadoAtualSala, EventoParticipante, 
                        Presenca, RFIDTag, Ocorrencia)
from datetime import datetime, time
import re

router = APIRouter(prefix="/seguranca", tags=["seguranca"])
templates = Jinja2Templates(directory="public")


def usuario_eh_seguranca(usuario: Usuario) -> bool:
    return usuario.tipo == "seguranca"


def filtro_inspecao_pendente_relatorio():
    return (
        Evento.tipo == "inspecao",
        Evento.status == "finalizado",
        or_(
            Evento.descricao == None,
            ~Evento.descricao.contains("[RELATÓRIO DE INSPEÇÃO]"),
        ),
    )

@router.get("/dashboard")
def dashboard_seguranca(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    agora = datetime.now()

    proximos_eventos = (
        db.query(Evento)
        .filter(
            Evento.status.in_(["agendado", "pendente"]),
            Evento.inicio_previsto > agora,
        )
        .order_by(Evento.inicio_previsto.asc())
        .all()
    )

    eventos_em_andamento = (
        db.query(Evento)
        .filter(Evento.status.in_(["ativo", "encerrando"]))
        .order_by(Evento.inicio_previsto.asc())
        .all()
    )

    aguardando_validacao = (
        db.query(Evento)
        .filter(*filtro_inspecao_pendente_relatorio())
        .order_by(Evento.fim_real.desc(), Evento.inicio_previsto.asc())
        .all()
    )

    salas = {sala.id_sala: sala for sala in db.query(Sala).all()}
    usuarios = {usuario.id_usuario: usuario for usuario in db.query(Usuario).all()}

    return templates.TemplateResponse(
        "seguranca/dashboard.html",
        {
            "request": request,
            "usuario": current_user,
            "proximos_eventos": proximos_eventos,
            "eventos_em_andamento": eventos_em_andamento,
            "aguardando_validacao": aguardando_validacao,
            "salas": salas,
            "usuarios": usuarios,
        },
    )

@router.get("/salas")
def visao_geral_salas(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    eventos_ativos = (
        db.query(Evento)
        .filter(Evento.status.in_(["agendado", "pendente", "ativo", "encerrando"]))
        .all()
    )

    estados_sala = db.query(EstadoAtualSala).all()

    usuarios = {usuario.id_usuario: usuario for usuario in db.query(Usuario).all()}

    eventos_por_sala = {}

    for evento in eventos_ativos:
        if evento.sala_id not in eventos_por_sala:
            eventos_por_sala[evento.sala_id] = []

        eventos_por_sala[evento.sala_id].append(evento)

    estados_por_sala = {
        estado.sala_id: estado
        for estado in estados_sala
    }

    return templates.TemplateResponse(
        "seguranca/salas.html",
        {
            "request": request,
            "usuario": current_user,
            "salas": salas,
            "eventos_por_sala": eventos_por_sala,
            "estados_por_sala": estados_por_sala,
            "usuarios": usuarios,
        },
    )

@router.get("/validacoes")
def listar_validacoes(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    eventos = (
        db.query(Evento)
        .filter(*filtro_inspecao_pendente_relatorio())
        .order_by(Evento.fim_real.desc(), Evento.inicio_previsto.asc())
        .all()
    )

    ids_inspecoes_automaticas = {
        rel.evento_destino_id
        for rel in db.query(EventoRelacao)
        .filter(EventoRelacao.tipo_relacao == "validacao_pos_projeto")
        .all()
    }

    salas = {sala.id_sala: sala for sala in db.query(Sala).all()}
    usuarios = {usuario.id_usuario: usuario for usuario in db.query(Usuario).all()}

    return templates.TemplateResponse(
        "seguranca/validacoes-lista.html",
        {
            "request": request,
            "usuario": current_user,
            "eventos": eventos,
            "salas": salas,
            "usuarios": usuarios,
            "ids_inspecoes_automaticas": ids_inspecoes_automaticas,
        },
    )


@router.get("/validacoes/{evento_id}")
def formulario_validacao(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            *filtro_inspecao_pendente_relatorio(),
        )
        .first()
    )

    if not evento:
        return RedirectResponse(
            url="/seguranca/validacoes",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    sala = db.query(Sala).filter(Sala.id_sala == evento.sala_id).first()

    host = db.query(Usuario).filter(Usuario.id_usuario == evento.host).first()

    is_pos_projeto = (
        db.query(EventoRelacao)
        .filter(
            EventoRelacao.evento_destino_id == evento.id_evento,
            EventoRelacao.tipo_relacao == "validacao_pos_projeto",
        )
        .first()
        is not None
    )

    return templates.TemplateResponse(
        "seguranca/validacao-form.html",
        {
            "request": request,
            "usuario": current_user,
            "evento": evento,
            "sala": sala,
            "host": host,
            "erro": None,
            "is_pos_projeto": is_pos_projeto,
        },
    )


@router.post("/validacoes/{evento_id}")
async def concluir_validacao(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()

    chave_devolvida = form.get("chave_devolvida")
    observacoes = form.get("observacoes")

    registrar_ocorrencia = form.get("registrar_ocorrencia")
    descricao_ocorrencia = form.get("descricao_ocorrencia")
    severidade = form.get("severidade") or "media"

    evento = (
        db.query(Evento)
        .filter(
            Evento.id_evento == evento_id,
            *filtro_inspecao_pendente_relatorio(),
        )
        .first()
    )

    if not evento:
        return RedirectResponse(
            url="/seguranca/validacoes",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    is_pos_projeto = (
        db.query(EventoRelacao)
        .filter(
            EventoRelacao.evento_destino_id == evento.id_evento,
            EventoRelacao.tipo_relacao == "validacao_pos_projeto",
        )
        .first()
        is not None
    )

    resumo_validacao = "\n\n[RELATÓRIO DE INSPEÇÃO]\n"

    if is_pos_projeto:
        resumo_validacao += f"Chave devolvida: {chave_devolvida or '-'}\n"

    resumo_validacao += f"Considerações: {observacoes if observacoes else '-'}\n"

    evento.descricao = (evento.descricao or "") + resumo_validacao

    if registrar_ocorrencia == "on" and descricao_ocorrencia:
        evento.descricao += (
            f"\n[OCORRÊNCIA - {severidade.upper()}]\n"
            f"{descricao_ocorrencia}\n"
        )

    db.commit()

    return RedirectResponse(
        url="/seguranca/validacoes",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.get("/api/salas/status")
def api_status_salas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.tipo != "seguranca":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso permitido apenas para segurança.",
        )

    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    resposta = []

    for sala in salas:
        estado = (
            db.query(EstadoAtualSala)
            .filter(EstadoAtualSala.sala_id == sala.id_sala)
            .first()
        )

        evento_ativo = (
            db.query(Evento)
            .filter(
                Evento.sala_id == sala.id_sala,
                Evento.status.in_(["ativo", "encerrando"]),
            )
            .order_by(Evento.inicio_real.desc())
            .first()
        )

        porta_aberta = estado.porta_aberta if estado else None

        if porta_aberta is None:
            status_visual = "Sem leitura"
            nivel = "offline"
        elif evento_ativo and porta_aberta:
            status_visual = "Em uso / porta aberta"
            nivel = "ocupada"
        elif evento_ativo and not porta_aberta:
            status_visual = "Em uso / porta fechada"
            nivel = "ocupada"
        elif not evento_ativo and porta_aberta:
            status_visual = "Aberta sem evento"
            nivel = "alerta"
        else:
            status_visual = "Livre / porta fechada"
            nivel = "livre"

        resposta.append({
            "sala_id": sala.id_sala,
            "numero": sala.numero,
            "nome": getattr(sala, "nome", None),
            "porta_aberta": porta_aberta,
            "tem_evento_ativo": evento_ativo is not None,
            "evento_id": evento_ativo.id_evento if evento_ativo else None,
            "evento_tipo": evento_ativo.tipo if evento_ativo else None,
            "status_evento": evento_ativo.status if evento_ativo else None,
            "status_visual": status_visual,
            "nivel": nivel,
            "atualizado_em": (
                estado.atualizado_em.isoformat()
                if estado and estado.atualizado_em
                else None
            ),
        })

    return resposta

@router.get("/auditoria")
def auditoria_eventos(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    tipo: str | None = None,
    status_evento: str | None = None,
    sala_id: int | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    somente_problemas: bool = False,
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    query = (
        db.query(Evento)
        .order_by(Evento.inicio_previsto.desc())
    )

    if tipo:
        query = query.filter(Evento.tipo == tipo)

    if status_evento:
        query = query.filter(Evento.status == status_evento)

    if sala_id:
        query = query.filter(Evento.sala_id == sala_id)

    # 🔥 filtro por data
    if data_inicio:
        inicio_dt = datetime.combine(
            datetime.strptime(data_inicio, "%Y-%m-%d").date(),
            time.min
        )
        query = query.filter(Evento.inicio_previsto >= inicio_dt)

    if data_fim:
        fim_dt = datetime.combine(
            datetime.strptime(data_fim, "%Y-%m-%d").date(),
            time.max
        )
        query = query.filter(Evento.inicio_previsto <= fim_dt)

    eventos = query.all()

    eventos_auditados = []

    for evento in eventos:
        presencas_count = (
            db.query(Presenca)
            .filter(Presenca.id_evento == evento.id_evento)
            .count()
        )

        alertas = []

        if evento.status == "nao_realizado":
            alertas.append("Evento não realizado")

        if evento.status == "cancelado":
            alertas.append("Evento cancelado")

        if evento.status == "aguardando_validacao":
            alertas.append("Aguardando validação")

        if evento.status == "finalizado" and presencas_count == 0:
            alertas.append("Finalizado sem presenças")

        if evento.status in ["ativo", "encerrando"]:
            alertas.append("Evento ainda aberto")

        if evento.inicio_previsto and evento.inicio_real:
            atraso_inicio = (evento.inicio_real - evento.inicio_previsto).total_seconds() / 60
            if atraso_inicio > 15:
                alertas.append("Início fora da tolerância")

        if evento.fim_previsto and evento.fim_real:
            atraso_fim = (evento.fim_real - evento.fim_previsto).total_seconds() / 60
            if atraso_fim > 15:
                alertas.append("Fim fora da tolerância")

        nivel = "OK"
        if alertas:
            nivel = "Atenção"

        if any(
            termo in " ".join(alertas).lower()
            for termo in ["não realizado", "sem presenças", "fora da tolerância"]
        ):
            nivel = "Crítico"

        if somente_problemas and nivel == "OK":
            continue

        sala_label = "-"
        if evento.sala:
            sala_label = (
                getattr(evento.sala, "nome", None)
                or getattr(evento.sala, "descricao", None)
                or getattr(evento.sala, "identificacao", None)
                or f"Sala {evento.sala.id_sala}"
            )

        eventos_auditados.append({
            "evento": evento,
            "host": evento.host_usuario,
            "presencas_count": presencas_count,
            "alertas": alertas,
            "nivel": nivel,
            "sala_label": sala_label,
        })

    # 🔥 salas para filtro com label seguro
    salas_db = db.query(Sala).order_by(Sala.id_sala).all()

    salas = []
    for sala in salas_db:
        label = (
            getattr(sala, "nome", None)
            or getattr(sala, "descricao", None)
            or getattr(sala, "identificacao", None)
            or f"Sala {sala.id_sala}"
        )

        salas.append({
            "id_sala": sala.id_sala,
            "label": label,
        })

    return templates.TemplateResponse(
        "seguranca/auditoria.html",
        {
            "request": request,
            "usuario": current_user,
            "eventos_auditados": eventos_auditados,
            "salas": salas,
            "filtros": {
                "tipo": tipo,
                "status_evento": status_evento,
                "sala_id": sala_id,
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "somente_problemas": somente_problemas,
            },
        },
    )

@router.get("/auditoria/{evento_id}")
def auditoria_evento_detalhe(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    evento = db.query(Evento).filter(Evento.id_evento == evento_id).first()

    if not evento:
        return RedirectResponse(
            url="/seguranca/auditoria",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    participantes = (
        db.query(EventoParticipante, Usuario)
        .join(Usuario, Usuario.id_usuario == EventoParticipante.usuario_id)
        .filter(EventoParticipante.evento_id == evento_id)
        .order_by(Usuario.nome)
        .all()
    )

    presencas = (
        db.query(Presenca, Usuario)
        .join(Usuario, Usuario.id_usuario == Presenca.id_usuario)
        .filter(Presenca.id_evento == evento_id)
        .order_by(Presenca.data_hora)
        .all()
    )

    linha_do_tempo = []

    if evento.inicio_previsto:
        linha_do_tempo.append({"data_hora": evento.inicio_previsto, "descricao": "Início previsto"})

    if evento.inicio_real:
        linha_do_tempo.append({"data_hora": evento.inicio_real, "descricao": "Evento iniciado"})

    for presenca, usuario in presencas:
        linha_do_tempo.append({
            "data_hora": presenca.data_hora,
            "descricao": f"{usuario.nome} registrou {presenca.tipo}",
        })

    if evento.fim_previsto:
        linha_do_tempo.append({"data_hora": evento.fim_previsto, "descricao": "Fim previsto"})

    if evento.fim_real:
        linha_do_tempo.append({"data_hora": evento.fim_real, "descricao": "Evento finalizado"})

    linha_do_tempo.sort(key=lambda x: x["data_hora"] or evento.criado_em)

    alertas = []

    if evento.status == "nao_realizado":
        alertas.append("Evento não realizado")

    if evento.status == "cancelado":
        alertas.append("Evento cancelado")

    if evento.status == "aguardando_validacao":
        alertas.append("Aguardando validação")

    if evento.status == "finalizado" and not presencas:
        alertas.append("Finalizado sem presenças")

    if evento.status in ["ativo", "encerrando"]:
        alertas.append("Evento ainda aberto")

    return templates.TemplateResponse(
        "seguranca/auditoria-detalhe.html",
        {
            "request": request,
            "usuario": current_user,
            "evento": evento,
            "participantes": participantes,
            "presencas": presencas,
            "linha_do_tempo": linha_do_tempo,
            "alertas": alertas,
        },
    )

@router.get("/rfid")
def listar_alunos_rfid(
    request: Request,
    busca: str | None = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    query = (
        db.query(Usuario)
        .filter(Usuario.tipo == "aluno")
        .order_by(Usuario.nome.asc())
    )

    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter(
            or_(
                Usuario.nome.ilike(termo),
                Usuario.email.ilike(termo),
            )
        )

    alunos = query.all()

    tags_ativas = (
        db.query(RFIDTag)
        .filter(RFIDTag.ativa == True)
        .all()
    )

    tags_por_usuario = {
        tag.usuario_id: tag
        for tag in tags_ativas
    }

    return templates.TemplateResponse(
        "seguranca/rfid-lista.html",
        {
            "request": request,
            "usuario": current_user,
            "alunos": alunos,
            "tags_por_usuario": tags_por_usuario,
            "busca": busca or "",
        },
    )

@router.get("/rfid/{usuario_id}")
def editar_rfid_usuario(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.id_usuario == usuario_id,
            Usuario.tipo == "aluno",
        )
        .first()
    )

    if not usuario:
        return RedirectResponse(
            url="/usuarios/",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    tag_ativa = (
        db.query(RFIDTag)
        .filter(
            RFIDTag.usuario_id == usuario.id_usuario,
            RFIDTag.ativa == True,
        )
        .order_by(RFIDTag.emitida_em.desc())
        .first()
    )

    return templates.TemplateResponse(
        "seguranca/rfid-form.html",
        {
            "request": request,
            "usuario": current_user,
            "aluno": usuario,
            "tag_ativa": tag_ativa,
            "erro": None,
        },
    )

@router.post("/rfid/{usuario_id}")
async def substituir_rfid(
    usuario_id: int,
    request: Request,
    nova_tag: str = Form(...),
    motivo: str = Form("Substituição autorizada pela segurança"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(
            url="/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    aluno = (
        db.query(Usuario)
        .filter(
            Usuario.id_usuario == usuario_id,
            Usuario.tipo == "aluno",
        )
        .first()
    )

    if not aluno:
        return RedirectResponse(
            url="/seguranca/rfid",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    nova_tag = nova_tag.strip().upper()
    motivo = motivo.strip()

    tag_ativa = (
        db.query(RFIDTag)
        .filter(
            RFIDTag.usuario_id == aluno.id_usuario,
            RFIDTag.ativa == True,
        )
        .order_by(RFIDTag.emitida_em.desc())
        .first()
    )

    def render_erro(msg):
        return templates.TemplateResponse(
            "seguranca/rfid-form.html",
            {
                "request": request,
                "usuario": current_user,
                "aluno": aluno,
                "tag_ativa": tag_ativa,
                "erro": msg,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    HEX_RE = re.compile(r"^[0-9A-F]{8,24}$")

    if not HEX_RE.match(nova_tag):
        return render_erro(
            "Código RFID inválido."
        )

    agora = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).replace(tzinfo=None)

    tag_existente = (
        db.query(RFIDTag)
        .filter(
            RFIDTag.codigo == nova_tag
        )
        .first()
    )

    if tag_existente:

        if tag_existente.usuario_id != aluno.id_usuario:
            return render_erro(
                "Essa TAG já pertence a outro usuário."
            )

        if tag_existente.ativa:
            return render_erro(
                "Essa TAG já está ativa para este aluno."
            )

    tags_ativas = (
        db.query(RFIDTag)
        .filter(
            RFIDTag.usuario_id == aluno.id_usuario,
            RFIDTag.ativa == True,
        )
        .all()
    )

    for tag in tags_ativas:
        tag.ativa = False
        tag.desativada_em = agora
        tag.motivo_desativacao = (
            f"{motivo} | Segurança: {current_user.nome}"
        )

    if tag_existente:

        tag_existente.ativa = True
        tag_existente.emitida_em = agora
        tag_existente.desativada_em = None
        tag_existente.motivo_desativacao = None

    else:

        db.add(
            RFIDTag(
                usuario_id=aluno.id_usuario,
                codigo=nova_tag,
                ativa=True,
                emitida_em=agora,
            )
        )

    try:
        db.commit()

    except IntegrityError:

        db.rollback()

        return render_erro(
            "Falha ao substituir RFID."
        )

    return RedirectResponse(
        url=f"/seguranca/rfid/{aluno.id_usuario}",
        status_code=status.HTTP_303_SEE_OTHER,
    )

@router.get("/ocorrencias")
def listar_ocorrencias(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    ocorrencias = (
        db.query(Ocorrencia)
        .order_by(Ocorrencia.data_ocorrencia.desc())
        .all()
    )

    eventos = {e.id_evento: e for e in db.query(Evento).all()}
    salas = {s.id_sala: s for s in db.query(Sala).all()}
    usuarios = {u.id_usuario: u for u in db.query(Usuario).all()}

    return templates.TemplateResponse(
        "seguranca/ocorrencias-lista.html",
        {
            "request": request,
            "usuario": current_user,
            "ocorrencias": ocorrencias,
            "eventos": eventos,
            "salas": salas,
            "usuarios": usuarios,
        },
    )


@router.get("/ocorrencias/nova")
def nova_ocorrencia_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    eventos = (
        db.query(Evento)
        .filter(
            Evento.status.in_([
                "ativo",
                "encerrando",
                "finalizado",
                "nao_realizado",
                "cancelado",
            ])
        )
        .order_by(Evento.inicio_previsto.desc())
        .limit(100)
        .all()
    )
    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    return templates.TemplateResponse(
        "seguranca/ocorrencia-form.html",
        {
            "request": request,
            "usuario": current_user,
            "eventos": eventos,
            "salas": salas,
            "erro": None,
        },
    )


@router.post("/ocorrencias")
def criar_ocorrencia(
    request: Request,
    tipo: str = Form(...),
    descricao: str = Form(...),
    severidade: str = Form("media"),
    evento_id: int | None = Form(None),
    sala_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    tipo = tipo.strip()
    descricao = descricao.strip()
    severidade = severidade.strip() if severidade else "media"

    eventos = (
        db.query(Evento)
        .filter(
            Evento.status.in_([
                "ativo",
                "encerrando",
                "finalizado",
                "nao_realizado",
                "cancelado",
            ])
        )
        .order_by(Evento.inicio_previsto.desc())
        .limit(100)
        .all()
    )
    salas = db.query(Sala).order_by(Sala.numero.asc()).all()

    def render_erro(msg: str):
        return templates.TemplateResponse(
            "seguranca/ocorrencia-form.html",
            {
                "request": request,
                "usuario": current_user,
                "eventos": eventos,
                "salas": salas,
                "erro": msg,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not tipo:
        return render_erro("Informe o tipo da ocorrência.")

    if not descricao:
        return render_erro("Informe a descrição/relatório da ocorrência.")

    if severidade not in ["baixa", "media", "alta"]:
        return render_erro("Severidade inválida.")

    if evento_id == 0:
        evento_id = None

    if sala_id == 0:
        sala_id = None

    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)

    ocorrencia = Ocorrencia(
        evento_id=evento_id,
        sala_id=sala_id,
        registrada_por=current_user.id_usuario,
        tipo=tipo,
        descricao=descricao,
        data_ocorrencia=agora,
        severidade=severidade,
        resolvida=False,
    )

    db.add(ocorrencia)
    db.commit()

    return RedirectResponse(
        url="/seguranca/ocorrencias",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/ocorrencias/{ocorrencia_id}/resolver")
def resolver_ocorrencia(
    ocorrencia_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not usuario_eh_seguranca(current_user):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    ocorrencia = (
        db.query(Ocorrencia)
        .filter(Ocorrencia.id_ocorrencia == ocorrencia_id)
        .first()
    )

    if ocorrencia:
        ocorrencia.resolvida = True
        ocorrencia.resolvida_em = datetime.now(
            ZoneInfo("America/Sao_Paulo")
        ).replace(tzinfo=None)

        db.commit()

    return RedirectResponse(
        url="/seguranca/ocorrencias",
        status_code=status.HTTP_303_SEE_OTHER,
    )