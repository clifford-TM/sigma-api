from sqlalchemy import Integer, String, Enum
from sqlalchemy.orm import Mapped, mapped_column

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