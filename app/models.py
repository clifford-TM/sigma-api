from datetime import datetime

from sqlalchemy import Integer, String, Enum, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(
        Enum("aluno", "professor", "seguranca", "tecnico", "admin", name="usuarios_tipo"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(191), unique=True, nullable=False)
    senha: Mapped[str] = mapped_column(String(60), nullable=False)


class RFIDTag(Base):
    __tablename__ = "rfid_tags"

    id_rfid_tag: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    emitida_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    desativada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    motivo_desativacao: Mapped[str | None] = mapped_column(String(255), nullable=True)

class Evento(Base):
    __tablename__ = "eventos"

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(
        Enum("aula", "projeto", "limpeza", "inspecao", "manutencao", name="eventos_tipo"),
        nullable=False,
    )
    host: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"), nullable=False)
    autorizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id_usuario"), nullable=True)
    forma_inicio: Mapped[str | None] = mapped_column(
        Enum("app", "seguranca", "gatilho_porta", name="eventos_forma_inicio"),
        nullable=True,
    )
    confirmado_por_rfid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    motivo_nao_realizacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sala_id: Mapped[int] = mapped_column(ForeignKey("salas.id_sala"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "agendado",
            "pendente",
            "ativo",
            "encerrando",
            "aguardando_validacao",
            "finalizado",
            "cancelado",
            "nao_realizado",
            name="eventos_status",
        ),
        nullable=False,
    )
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    inicio_previsto: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fim_previsto: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    inicio_real: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fim_real: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)