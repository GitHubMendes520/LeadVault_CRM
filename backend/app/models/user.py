from datetime import datetime, timedelta

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="BROKER")
    full_name = Column(String)
    creci = Column(String)
    data_nascimento = Column(String)
    telefone = Column(String)
    email_pessoal = Column(String)
    documento = Column(String)
    observacoes = Column(String)
    pais_operacao = Column(String, default="BR")
    idioma = Column(String, default="pt")
    last_seen_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    @property
    def is_online(self):
        if not self.last_seen_at:
            return False

        return datetime.utcnow() - self.last_seen_at <= timedelta(minutes=2)
