from fastapi import APIRouter, Header, HTTPException
from typing import Optional

from app.schemas import DevicePollRequest, DeviceCommandResponse, DeviceReplyRequest

router = APIRouter(prefix="/api/dispositivo", tags=["dispositivo"])

# depois vamos tirar isso do código e jogar em .env
DEVICE_TOKEN = "sigma-esp-teste-123"

# armazenamento temporário em memória só para teste
pending_commands = {}
command_counter = 1


def validar_token(x_device_token: Optional[str]) -> None:
    if x_device_token != DEVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Token de dispositivo inválido")


@router.post("/enviar-teste")
def enviar_teste_oled(
    dispositivo_id: int,
    mensagem: str,
):
    global command_counter

    command_id = command_counter
    command_counter += 1

    pending_commands[dispositivo_id] = {
        "command_id": command_id,
        "comando": "mostrar_oled",
        "mensagem": mensagem,
    }

    return {
        "ok": True,
        "message": "Comando de teste registrado",
        "command_id": command_id,
        "dispositivo_id": dispositivo_id,
    }


@router.post("/poll", response_model=DeviceCommandResponse)
def poll_dispositivo(
    payload: DevicePollRequest,
    x_device_token: Optional[str] = Header(default=None),
):
    validar_token(x_device_token)

    cmd = pending_commands.get(payload.dispositivo_id)

    if not cmd:
        return DeviceCommandResponse(ok=True, comando="nenhum")

    return DeviceCommandResponse(
        ok=True,
        comando=cmd["comando"],
        command_id=cmd["command_id"],
        mensagem=cmd["mensagem"],
    )


@router.post("/responder")
def responder_comando(
    payload: DeviceReplyRequest,
    x_device_token: Optional[str] = Header(default=None),
):
    validar_token(x_device_token)

    cmd = pending_commands.get(payload.dispositivo_id)

    if not cmd:
        raise HTTPException(status_code=404, detail="Nenhum comando pendente para este dispositivo")

    if cmd["command_id"] != payload.command_id:
        raise HTTPException(status_code=400, detail="command_id não corresponde ao comando pendente")

    # remove o comando pendente após confirmar execução
    del pending_commands[payload.dispositivo_id]

    return {
        "ok": True,
        "message": "Resposta do dispositivo registrada",
        "command_id": payload.command_id,
        "status": payload.status,
        "detalhe": payload.detalhe,
    }