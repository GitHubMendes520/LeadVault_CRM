from datetime import datetime

from pydantic import BaseModel


class LeadResponse(BaseModel):
    id: int
    nome: str | None = None
    contato: str | None = None
    email: str | None = None
    site: str | None = None
    endereco: str | None = None
    instagram: str | None = None
    linkedin: str | None = None
    facebook: str | None = None
    redes_sociais: str | None = None
    observacoes: str | None = None
    nicho: str | None = None
    pais: str | None = None
    score: int | None = None
    valor_negocio: float | None = None
    pipeline: str | None = None
    pipeline_updated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    assigned_to_user_id: int | None = None

    model_config = {
        "from_attributes": True,
    }


class LeadPipelineUpdate(BaseModel):
    pipeline: str


class LeadAssignUpdate(BaseModel):
    assigned_to_user_id: int | None = None


class LeadUpdate(BaseModel):
    nome: str | None = None
    contato: str | None = None
    email: str | None = None
    site: str | None = None
    endereco: str | None = None
    instagram: str | None = None
    linkedin: str | None = None
    facebook: str | None = None
    redes_sociais: str | None = None
    observacoes: str | None = None
    nicho: str | None = None
    pais: str | None = None
    score: int | None = None
    valor_negocio: float | None = None
    pipeline: str | None = None
    assigned_to_user_id: int | None = None
