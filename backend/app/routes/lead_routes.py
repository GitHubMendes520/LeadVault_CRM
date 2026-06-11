from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.lead import Lead
from app.models.lead_event import LeadEvent
from app.models.user import User
from app.schemas.lead_schema import LeadAssignUpdate, LeadEventCreate, LeadEventResponse, LeadPipelineUpdate, LeadResponse, LeadUpdate

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


def get_actor(
    x_actor_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if x_actor_id is None:
        raise HTTPException(status_code=403, detail="Usuario nao identificado")

    actor = db.query(User).filter(User.id == x_actor_id, User.is_active.is_(True)).first()
    if not actor:
        raise HTTPException(status_code=403, detail="Usuario nao identificado")

    return actor


def broker_ids_for_manager(db: Session, manager_id: int):
    return [
        broker_id
        for (broker_id,) in (
            db.query(User.id)
            .filter(User.role == "BROKER", User.manager_id == manager_id, User.is_active.is_(True))
            .all()
        )
    ]


def apply_actor_scope(query, db: Session, actor: User | None):
    if not actor or actor.role == "ROOT":
        return query

    if actor.role == "BROKER":
        return query.filter(Lead.assigned_to_user_id == actor.id)

    if actor.role == "GERENTE":
        return query.filter(Lead.assigned_to_user_id.in_(broker_ids_for_manager(db, actor.id)))

    return query.filter(False)


def ensure_lead_visible_to_actor(db: Session, lead: Lead, actor: User | None):
    if not actor or actor.role == "ROOT":
        return

    if actor.role == "BROKER" and lead.assigned_to_user_id == actor.id:
        return

    if actor.role == "GERENTE" and lead.assigned_to_user_id in broker_ids_for_manager(db, actor.id):
        return

    raise HTTPException(status_code=403, detail="Lead fora da sua estrutura")


def actor_label(actor: User | None):
    if not actor:
        return "Sistema"

    return actor.full_name or actor.username


def add_lead_event(db: Session, lead: Lead, actor: User | None, event_type: str, message: str):
    db.add(
        LeadEvent(
            lead_id=lead.id,
            actor_id=actor.id if actor else None,
            actor_name=actor_label(actor),
            event_type=event_type,
            message=message,
        )
    )


@router.get("/", response_model=list[LeadResponse])
def list_leads(
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_actor),
    search: str | None = None,
    pipeline: str | None = None,
    assigned_to_user_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    query = apply_actor_scope(db.query(Lead), db, actor)

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
                Lead.estado.ilike(term),
                Lead.cidade.ilike(term),
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
    actor: User | None = Depends(get_actor),
    assigned_to_user_id: int | None = None,
    limit_per_stage: int = Query(default=25, ge=1, le=100),
):
    board = {}

    for stage in PIPELINE_STAGES:
        query = apply_actor_scope(db.query(Lead).filter(Lead.pipeline == stage), db, actor)

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
def lead_inventory(
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin_actor),
):
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
    estados = (
        db.query(Lead.estado, func.count(Lead.id))
        .filter(Lead.assigned_to_user_id.is_(None), Lead.estado.isnot(None), Lead.estado != "")
        .group_by(Lead.estado)
        .order_by(func.count(Lead.id).desc(), Lead.estado)
        .all()
    )
    cidades = (
        db.query(Lead.cidade, func.count(Lead.id))
        .filter(Lead.assigned_to_user_id.is_(None), Lead.cidade.isnot(None), Lead.cidade != "")
        .group_by(Lead.cidade)
        .order_by(func.count(Lead.id).desc(), Lead.cidade)
        .all()
    )
    combinacoes = (
        db.query(Lead.nicho, Lead.pais, Lead.estado, Lead.cidade, func.count(Lead.id))
        .filter(Lead.assigned_to_user_id.is_(None))
        .group_by(Lead.nicho, Lead.pais, Lead.estado, Lead.cidade)
        .all()
    )

    return {
        "total_livre": total_free,
        "nichos": [{"nome": nicho, "total": total} for nicho, total in nichos],
        "paises": [{"nome": pais, "total": total} for pais, total in paises],
        "estados": [{"nome": estado, "total": total} for estado, total in estados],
        "cidades": [{"nome": cidade, "total": total} for cidade, total in cidades],
        "combinacoes": [
            {
                "nicho": nicho,
                "pais": pais,
                "estado": estado,
                "cidade": cidade,
                "total": total,
            }
            for nicho, pais, estado, cidade, total in combinacoes
        ],
    }


@router.get("/{lead_id}/events", response_model=list[LeadEventResponse])
def list_lead_events(
    lead_id: int,
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_actor),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    ensure_lead_visible_to_actor(db, lead, actor)

    return (
        db.query(LeadEvent)
        .filter(LeadEvent.lead_id == lead.id)
        .order_by(LeadEvent.created_at.desc(), LeadEvent.id.desc())
        .limit(100)
        .all()
    )


@router.post("/{lead_id}/events", response_model=LeadEventResponse)
def create_lead_note(
    lead_id: int,
    payload: LeadEventCreate,
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_actor),
):
    note = payload.message.strip()
    if not note:
        raise HTTPException(status_code=400, detail="Nota vazia")

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    ensure_lead_visible_to_actor(db, lead, actor)

    event = LeadEvent(
        lead_id=lead.id,
        actor_id=actor.id if actor else None,
        actor_name=actor_label(actor),
        event_type="NOTA",
        message=note,
    )
    db.add(event)
    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{lead_id}/pipeline", response_model=LeadResponse)
def update_lead_pipeline(
    lead_id: int,
    payload: LeadPipelineUpdate,
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_actor),
):
    stage = payload.pipeline.upper()

    if stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=400, detail="Etapa de pipeline invalida")

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    ensure_lead_visible_to_actor(db, lead, actor)
    if lead.pipeline != stage:
        previous_stage = lead.pipeline or "SEM ETAPA"
        lead.pipeline_updated_at = datetime.utcnow()
        add_lead_event(
            db,
            lead,
            actor,
            "PIPELINE",
            f"Moveu de {previous_stage} para {stage}",
        )
    lead.pipeline = stage
    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead


@router.patch("/{lead_id}/assign", response_model=LeadResponse)
def assign_lead(
    lead_id: int,
    payload: LeadAssignUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin_actor),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    ensure_lead_visible_to_actor(db, lead, actor)
    if actor.role == "GERENTE" and payload.assigned_to_user_id not in broker_ids_for_manager(db, actor.id):
        raise HTTPException(status_code=403, detail="Gerente pode mover lead apenas dentro da propria equipe")

    previous_broker_id = lead.assigned_to_user_id
    lead.assigned_to_user_id = payload.assigned_to_user_id
    lead.updated_at = datetime.utcnow()
    add_lead_event(
        db,
        lead,
        actor,
        "ATRIBUICAO",
        f"Broker alterado de {previous_broker_id or 'banco'} para {payload.assigned_to_user_id or 'banco'}",
    )
    db.commit()
    db.refresh(lead)
    return lead


@router.patch("/{lead_id}/return-to-bank", response_model=LeadResponse)
def return_lead_to_bank(
    lead_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin_actor),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    ensure_lead_visible_to_actor(db, lead, actor)
    lead.assigned_to_user_id = None
    lead.pipeline = "NOVO LEAD"
    lead.pipeline_updated_at = datetime.utcnow()
    lead.updated_at = datetime.utcnow()
    add_lead_event(db, lead, actor, "BANCO", "Lead voltou para o banco")
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin_actor),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    ensure_lead_visible_to_actor(db, lead, actor)
    add_lead_event(db, lead, actor, "EXCLUSAO", "Lead excluido definitivamente")
    db.delete(lead)
    db.commit()
    return {"deleted": True, "lead_id": lead_id}


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_actor),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado")

    ensure_lead_visible_to_actor(db, lead, actor)
    updates = payload.model_dump(exclude_unset=True)

    if "pipeline" in updates and updates["pipeline"]:
        stage = updates["pipeline"].upper()
        if stage not in PIPELINE_STAGES:
            raise HTTPException(status_code=400, detail="Etapa de pipeline invalida")
        if lead.pipeline != stage:
            previous_stage = lead.pipeline or "SEM ETAPA"
            lead.pipeline_updated_at = datetime.utcnow()
            add_lead_event(
                db,
                lead,
                actor,
                "PIPELINE",
                f"Moveu de {previous_stage} para {stage}",
            )
        updates["pipeline"] = stage

    tracked_fields = {
        "nome",
        "contato",
        "email",
        "site",
        "instagram",
        "linkedin",
        "facebook",
        "redes_sociais",
        "nicho",
        "pais",
        "score",
        "valor_negocio",
        "endereco",
        "observacoes",
    }
    changed_fields = [
        field
        for field, value in updates.items()
        if field in tracked_fields and str(getattr(lead, field, "") or "") != str(value or "")
    ]

    for field, value in updates.items():
        setattr(lead, field, value)

    lead.updated_at = datetime.utcnow()
    if changed_fields:
        add_lead_event(
            db,
            lead,
            actor,
            "EDICAO",
            f"Editou dados do lead: {', '.join(changed_fields)}",
        )
    db.commit()
    db.refresh(lead)
    return lead
