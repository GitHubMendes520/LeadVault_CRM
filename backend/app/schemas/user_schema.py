from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    manager_id: int | None = None
    full_name: str | None = None
    role: str = "BROKER"
    creci: str | None = None
    data_nascimento: str | None = None
    telefone: str | None = None
    email_pessoal: str | None = None
    documento: str | None = None
    observacoes: str | None = None
    pais_operacao: str | None = "BR"
    estado_operacao: str | None = None
    cidade_operacao: str | None = None
    idioma: str | None = "pt"


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    manager_id: int | None = None
    full_name: str | None = None
    role: str | None = None
    creci: str | None = None
    data_nascimento: str | None = None
    telefone: str | None = None
    email_pessoal: str | None = None
    documento: str | None = None
    observacoes: str | None = None
    pais_operacao: str | None = None
    estado_operacao: str | None = None
    cidade_operacao: str | None = None
    idioma: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    manager_id: int | None = None
    username: str
    role: str
    full_name: str | None = None
    creci: str | None = None
    data_nascimento: str | None = None
    telefone: str | None = None
    email_pessoal: str | None = None
    documento: str | None = None
    observacoes: str | None = None
    pais_operacao: str | None = None
    estado_operacao: str | None = None
    cidade_operacao: str | None = None
    idioma: str | None = None
    last_seen_at: datetime | None = None
    is_online: bool = False
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class AssignLeadsRequest(BaseModel):
    broker_id: int
    limit: int = 100
    nicho: str | None = None
    pais: str | None = None
    estado: str | None = None
    cidade: str | None = None


class ReturnLeadsRequest(BaseModel):
    broker_id: int | None = None
    limit: int | None = None
    all: bool = False
    nicho: str | None = None
    pais: str | None = None
    estado: str | None = None
    cidade: str | None = None
