from datetime import datetime
import re
import requests

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Evento, Dispositivo, RFIDTag, Usuario, Presenca
from app.schemas import TagAuthRequest, ParticipantePayload, CadernoFinalPayload
router = APIRouter(prefix="/eventos", tags=["eventos"])


# helpers
def normalizar_uid(uid: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", uid).upper()


def obter_dispositivo_da_sala(db: Session, sala_id: int) -> Dispositivo | None:
    return (
        db.query(Dispositivo)
        .filter(
            Dispositivo.sala_id == sala_id,
            Dispositivo.ativo == True
        )
        .first()
    )


def montar_url_esp(dispositivo: Dispositivo, rota: str) -> str:
    """
    Ajuste conforme seu model:
    - se tiver dispositivo.ip_local -> usar
    - se tiver dispositivo.endpoint -> usar direto
    """
    host = getattr(dispositivo, "ip_local", None) or getattr(dispositivo, "endereco", None)
    if not host:
        raise HTTPException(
            status_code=500,
            detail="Dispositivo sem IP/endereço cadastrado."
        )

    return f"http://{host}{rota}"


# =========================
# Professor -> Backend -> ESP
# =========================

@router.post("/{evento_id}/disparar-inicio")
def disparar_inicio_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    evento = db.query(Evento).filter(Evento.id_evento == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    dispositivo = obter_dispositivo_da_sala(db, evento.sala_id)
    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo da sala não encontrado.")

    payload = {
        "evento_id": evento.id_evento,
        "sala_id": evento.sala_id,
        "host_id": evento.host,
        "tipo": evento.tipo,
        "host_nome": current_user.nome,
    }

    url_esp = montar_url_esp(dispositivo, "/evento/iniciar")

    try:
        resp = requests.post(url_esp, json=payload, timeout=5)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao comunicar com o ESP: {e}"
        )

    return {
        "ok": True,
        "mensagem": "Comando de início enviado ao ESP.",
        "esp_url": url_esp,
        "esp_resposta": resp.json() if resp.content else {}
    }


@router.post("/{evento_id}/disparar-encerramento")
def disparar_encerramento_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    evento = db.query(Evento).filter(Evento.id_evento == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    dispositivo = obter_dispositivo_da_sala(db, evento.sala_id)
    if not dispositivo:
        raise HTTPException(status_code=404, detail="Dispositivo da sala não encontrado.")

    url_esp = montar_url_esp(dispositivo, "/evento/encerrar")

    try:
        resp = requests.post(url_esp, json={"evento_id": evento.id_evento}, timeout=5)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao comunicar com o ESP: {e}"
        )

    return {
        "ok": True,
        "mensagem": "Comando de encerramento enviado ao ESP.",
        "esp_url": url_esp,
        "esp_resposta": resp.json() if resp.content else {}
    }


# =========================
# ESP -> Backend
# =========================

@router.post("/{evento_id}/autorizar-inicio")
def autorizar_inicio_evento(
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
            RFIDTag.ativa == True
        )
        .first()
    )

    if not tag:
        raise HTTPException(status_code=403, detail="Tag não cadastrada.")

    usuario = db.query(Usuario).filter(Usuario.id_usuario == tag.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=403, detail="Usuário da tag não encontrado.")

    # Regra simples:
    # só o host do evento pode autorizar início
    if usuario.id_usuario != evento.host:
        raise HTTPException(status_code=403, detail="Usuário não autorizado para iniciar o evento.")

    evento.status = "ativo"
    if hasattr(evento, "inicio_real") and not evento.inicio_real:
        evento.inicio_real = datetime.now()

    db.commit()

    return {
        "ok": True,
        "mensagem": "Início autorizado.",
        "usuario_id": usuario.id_usuario,
        "usuario_nome": usuario.nome,
        "evento_id": evento.id_evento,
    }


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
            RFIDTag.ativa == True
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
                RFIDTag.ativa == True
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
    if hasattr(evento, "fim_real") and not evento.fim_real:
        evento.fim_real = datetime.now()

    db.commit()

    return {
        "ok": True,
        "mensagem": "Caderno final recebido.",
        "evento_id": payload.evento_id,
        "presencas_inseridas": inseridas,
    }