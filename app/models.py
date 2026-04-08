from datetime import datetime

from sqlalchemy import Integer, String, Enum, Boolean, DateTime, ForeignKey
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