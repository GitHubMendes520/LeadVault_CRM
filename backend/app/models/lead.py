from sqlalchemy import Column, ForeignKey, Integer, String
from app.database.connection import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    nome = Column(String)
    contato = Column(String)
    email = Column(String)
    site = Column(String)
    endereco = Column(String)
    instagram = Column(String)
    linkedin = Column(String)
    facebook = Column(String)
    redes_sociais = Column(String)
    observacoes = Column(String)

    nicho = Column(String)
    pais = Column(String)
    score = Column(Integer)

    pipeline = Column(String, default="NOVO LEAD")
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
