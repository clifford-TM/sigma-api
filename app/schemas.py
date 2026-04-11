from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class LoginForm(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1)


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    tipo: str
    email: EmailStr
    senha: str = Field(min_length=6)


class UsuarioOut(BaseModel):
    id_usuario: int
    nome: str
    tipo: str
    email: EmailStr

    class Config:
        from_attributes = True

class DevicePollRequest(BaseModel):
    dispositivo_id: int

class DeviceCommandResponse(BaseModel):
    ok: bool
    comando: str
    command_id: Optional[int] = None
    mensagem: Optional[str] = None

class DeviceReplyRequest(BaseModel):
    dispositivo_id: int
    command_id: int
    status: str
    detalhe: Optional[str] = None

class TagReadRequest(BaseModel):
    dispositivo_id: int
    tag_uid: str

class TagAuthRequest(BaseModel):
    uid: str
    device_id: str


class ParticipantePayload(BaseModel):
    uid: str
    timestamp: str


class CadernoFinalPayload(BaseModel):
    evento_id: int
    sala_id: int
    host_id: int
    tipo: str
    device_id: str
    room_id: str
    participantes: list[ParticipantePayload]
