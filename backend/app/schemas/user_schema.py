from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    role: str = "BROKER"
    creci: str | None = None
    data_nascimento: str | None = None
    telefone: str | None = None
    email_pessoal: str | None = None
    documento: str | None = None
    observacoes: str | None = None


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    full_name: str | None = None
    role: str | None = None
    creci: str | None = None
    data_nascimento: str | None = None
    telefone: str | None = None
    email_pessoal: str | None = None
    documento: str | None = None
    observacoes: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    full_name: str | None = None
    creci: str | None = None
    data_nascimento: str | None = None
    telefone: str | None = None
    email_pessoal: str | None = None
    documento: str | None = None
    observacoes: str | None = None
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class AssignLeadsRequest(BaseModel):
    broker_id: int
    limit: int = 100
    nicho: str | None = None
    pais: str | None = None


class ReturnLeadsRequest(BaseModel):
    broker_id: int | None = None
    limit: int | None = None
    all: bool = False
    nicho: str | None = None
    pais: str | None = None
