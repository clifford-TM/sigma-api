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

class EventoParticipante(Base):
    __tablename__ = "evento_participantes"

    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id_evento"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"), primary_key=True)
    papel: Mapped[str] = mapped_column(
        Enum("professor", "aluno", "seguranca", "tecnico", name="evento_participantes_papel"),
        nullable=False,
    )

class Presenca(Base):
    __tablename__ = "presencas"

    id_presenca: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_evento: Mapped[int] = mapped_column(ForeignKey("eventos.id_evento"), nullable=False)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"), nullable=False)
    dispositivo_id: Mapped[int | None] = mapped_column(ForeignKey("dispositivos.id_dispositivo"), nullable=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    tipo: Mapped[str] = mapped_column(
        Enum("entrada", "saida", name="presencas_tipo"),
        nullable=False,
    )
    origem: Mapped[str] = mapped_column(
        Enum("rfid", "ajuste_seguranca", "sincronizacao_dispositivo", name="presencas_origem"),
        nullable=False,
    )
    valido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

class EstadoSala(Base):
    __tablename__ = "estados_sala"

    id_estado_sala: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    cor: Mapped[str] = mapped_column(String(7), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)

class Sala(Base):
    __tablename__ = "salas"

    id_sala: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(
        Enum("sala", "laboratorio", "auditorio", name="salas_tipo"),
        nullable=False,
    )
    estado_atual_id: Mapped[int] = mapped_column(ForeignKey("estados_sala.id_estado_sala"), nullable=False)

class Dispositivo(Base):
    __tablename__ = "dispositivos"

    id_dispositivo: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sala_id: Mapped[int] = mapped_column(ForeignKey("salas.id_sala"), nullable=False)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    identificador_fisico: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ultima_comunicacao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

class Validacao(Base):
    __tablename__ = "validacoes"

    id_validacao: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id_evento"), nullable=False, unique=True)
    seguranca_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"), nullable=False)
    data_validacao: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("aprovado", "reprovado", "pendente", name="validacoes_status"),
        nullable=False,
    )
    observacoes: Mapped[str | None] = mapped_column(String(255), nullable=True)

class Ocorrencia(Base):
    __tablename__ = "ocorrencias"

    id_ocorrencia: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[int | None] = mapped_column(ForeignKey("eventos.id_evento"), nullable=True)
    sala_id: Mapped[int | None] = mapped_column(ForeignKey("salas.id_sala"), nullable=True)
    registrada_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id_usuario"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    data_ocorrencia: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    severidade: Mapped[str | None] = mapped_column(
        Enum("baixa", "media", "alta", name="ocorrencias_severidade"),
        nullable=True,
    )
    resolvida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)