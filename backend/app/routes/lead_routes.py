from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.lead import Lead
from app.models.user import User
from app.schemas.lead_schema import LeadAssignUpdate, LeadPipelineUpdate, LeadResponse, LeadUpdate

router = APIRouter(prefix="/leads", tags=["leads"])

PIPELINE_STAGES = [
    "NOVO LEAD",
    "ATENDIMENTO",
    "TENTATIVA DE CONTATO",
    "VISITA",
    "MONTAGEM DE PASTA",
    "VENDA GANHA",
    "PERDIDO",
]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin_actor(
    x_actor_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    actor = None

    if x_actor_id is not None:
        actor = db.query(User).filter(User.id == x_actor_id, User.is_active.is_(True)).first()

    if not actor or actor.role not in {"ROOT", "GERENTE"}:
        raise HTTPException(status_code=403, detail="Somente root ou gerente pode executar esta acao")

    return actor


@router.get("/", response_model=list[LeadResponse])
def list_leads(
    db: Session = Depends(get_db),
    search: str | None = None,
    pipeline: str | None = None,
    assigned_to_user_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(Lead)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Lead.nome.ilike(term),
                Lead.email.ilike(term),
                Lead.contato.ilike(term),
                Lead.site.ilike(term),
                Lead.nicho.ilike(term),
                Lead.pais.ilike(term),
            )
        )

    if pipeline:
        query = query.filter(Lead.pipeline == pipeline)

    if assigned_to_user_id is not None:
        query = query.filter(Lead.assigned_to_user_id == assigned_to_user_id)

    return (
        query.order_by(Lead.score.desc().nullslast(), Lead.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/kanban")
def kanban_leads(
    db: Session = Depends(get_db),
    assigned_to_user_id: int | None = None,
    limit_per_stage: int = Query(default=25, ge=1, le=100),
):
    board = {}

    for stage in PIPELINE_STAGES:
        query = db.query(Lead).filter(Lead.pipeline == stage)

        if assigned_to_user_id is not None:
            query = query.filter(Lead.assigned_to_user_id == assigned_to_user_id)

        leads = (
            query.order_by(Lead.score.desc().nullslast(), Lead.id)
            .limit(limit_per_stage)
            .all()
        )
        board[stage] = [LeadResponse.model_validate(lead).model_dump() for lead in leads]

    return {
        "stages": PIPELINE_STAGES,
        "board": board,
    }


@router.get("/inventory")
def lead_inventory(db: Session = Depends(get_db)):
    free_query = db.query(Lead).filter(Lead.assigned_to_user_id.is_(None))
    total_free = free_query.count()

    nichos = (
        db.query(Lead.nicho, func.count(Lead.id))
        .filter(Lead.assigned_to_user_id.is_(None), Lead.nicho.isnot(None), Lead.nicho != "")
        .group_by(Lead.nicho)
        .order_by(func.count(Lead.id).desc(), Lead.nicho)
        .all()
    )
    paises = (
        db.query(Lead.pais, func.count(Lead.id))
        .filter(Lead.assigned_to_user_id.is_(None), Lead.pais.isnot(None), Lead.pais != "")
        .group_by(Lead.pais)
        .order_by(func.count(Lead.id).desc(), Lead.pais)
        .all()
    )
    combinacoes = (
        db.query(Lead.nicho, Lead.pais, func.count(Lead.id))
        .filter(Lead.assigned_to_user_id.is_(None))
        .group_by(Lead.nicho, Lead.pais)
        .all()
    )

    return {
        "total_livre": total_free,
        "nichos": [{"nome": nicho, "total": total} for nicho, total in nichos],
        "paises": [{"nome": pais, "total": total} for pais, total in paises],
        "combinacoes": [
            {"nicho": nicho, "pais": pais, "total": total}
            for nicho, pais, total in combinacoes
        ],
    }


@router.patch("/{lead_id}/pipeline", response_model=LeadResponse)
def update_lead_pipeline(
    lead_id: int,
    payload: LeadPipelineUpdate,
    db: Session = Depends(get_db),
):
    stage = payload.pipeline.upper()

    if stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=400, detail="Etapa de pipeline invalida")

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    lead.pipeline = stage
    db.commit()
    db.refresh(lead)
    return lead


@router.patch("/{lead_id}/assign", response_model=LeadResponse)
def assign_lead(
    lead_id: int,
    payload: LeadAssignUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_actor),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    lead.assigned_to_user_id = payload.assigned_to_user_id
    db.commit()
    db.refresh(lead)
    return lead


@router.patch("/{lead_id}/return-to-bank", response_model=LeadResponse)
def return_lead_to_bank(
    lead_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_actor),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    lead.assigned_to_user_id = None
    lead.pipeline = "NOVO LEAD"
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_actor),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    db.delete(lead)
    db.commit()
    return {"deleted": True, "lead_id": lead_id}


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    updates = payload.model_dump(exclude_unset=True)

    if "pipeline" in updates and updates["pipeline"]:
        stage = updates["pipeline"].upper()
        if stage not in PIPELINE_STAGES:
            raise HTTPException(status_code=400, detail="Etapa de pipeline invalida")
        updates["pipeline"] = stage

    for field, value in updates.items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    return lead
