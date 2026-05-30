import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.database.connection import SessionLocal
from app.models.lead import Lead
from app.models.user import User
from app.schemas.user_schema import AssignLeadsRequest, LoginRequest, ReturnLeadsRequest, UserCreate, UserResponse, UserUpdate

ROOT_KEY = os.getenv("ROOT_KEY", "12345m*")

router = APIRouter(prefix="/users", tags=["users"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_root_key(x_root_key: str | None = Header(default=None)):
    if x_root_key != ROOT_KEY:
        raise HTTPException(status_code=403, detail="Acesso root negado")


def require_admin_actor(
    x_actor_id: int | None = Header(default=None),
    x_root_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if x_actor_id is None:
        if x_root_key == ROOT_KEY:
            return None
        raise HTTPException(status_code=403, detail="Acesso administrativo negado")

    actor = db.query(User).filter(User.id == x_actor_id, User.is_active.is_(True)).first()

    if not actor or actor.role not in {"ROOT", "GERENTE"}:
        raise HTTPException(status_code=403, detail="Somente root ou gerente pode executar esta acao")

    return actor


def require_root_actor(
    x_actor_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    actor = None

    if x_actor_id is not None:
        actor = db.query(User).filter(User.id == x_actor_id, User.is_active.is_(True)).first()

    if not actor or actor.role != "ROOT":
        raise HTTPException(status_code=403, detail="Somente root pode executar esta acao")

    return actor


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario inativo")

    return user


@router.get("/", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User | None = Depends(require_admin_actor),
):
    return db.query(User).order_by(User.id).all()


@router.get("/brokers/summary")
def broker_summary(
    db: Session = Depends(get_db),
    _: User | None = Depends(require_admin_actor),
):
    brokers = (
        db.query(User)
        .filter(User.role == "BROKER")
        .order_by(User.id)
        .all()
    )

    summary = []
    for broker in brokers:
        pipeline_counts = (
            db.query(Lead.pipeline, func.count(Lead.id))
            .filter(Lead.assigned_to_user_id == broker.id)
            .group_by(Lead.pipeline)
            .all()
        )
        counts = {pipeline: count for pipeline, count in pipeline_counts}
        total = sum(counts.values())

        summary.append(
            {
                "id": broker.id,
                "username": broker.username,
                "full_name": broker.full_name,
                "role": broker.role,
                "creci": broker.creci,
                "data_nascimento": broker.data_nascimento,
                "telefone": broker.telefone,
                "email_pessoal": broker.email_pessoal,
                "documento": broker.documento,
                "observacoes": broker.observacoes,
                "pais_operacao": broker.pais_operacao,
                "idioma": broker.idioma,
                "is_active": broker.is_active,
                "total_leads": total,
                "pipeline_counts": counts,
            }
        )

    return summary


@router.post("/", response_model=UserResponse)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User | None = Depends(require_admin_actor),
):
    role = payload.role.upper()

    if role not in {"ROOT", "GERENTE", "BROKER"}:
        raise HTTPException(status_code=400, detail="Role deve ser ROOT, GERENTE ou BROKER")

    if actor and actor.role == "GERENTE" and role != "BROKER":
        raise HTTPException(status_code=403, detail="Gerente pode cadastrar apenas broker")

    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Usuario ja existe")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
        creci=payload.creci,
        data_nascimento=payload.data_nascimento,
        telefone=payload.telefone,
        email_pessoal=payload.email_pessoal,
        documento=payload.documento,
        observacoes=payload.observacoes,
        pais_operacao=(payload.pais_operacao or "BR").upper(),
        idioma=(payload.idioma or "pt").lower(),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    actor: User | None = Depends(require_admin_actor),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    updates = payload.model_dump(exclude_unset=True)

    if actor and actor.role == "GERENTE":
        blocked_fields = {"role", "is_active"}
        if blocked_fields.intersection(updates):
            raise HTTPException(status_code=403, detail="Gerente nao pode alterar role ou status")
        if user.role != "BROKER":
            raise HTTPException(status_code=403, detail="Gerente pode editar apenas brokers")

    if "role" in updates and updates["role"]:
        role = updates["role"].upper()
        if role not in {"ROOT", "GERENTE", "BROKER"}:
            raise HTTPException(status_code=400, detail="Role deve ser ROOT, GERENTE ou BROKER")
        updates["role"] = role

    if "pais_operacao" in updates and updates["pais_operacao"]:
        updates["pais_operacao"] = updates["pais_operacao"].upper()

    if "idioma" in updates and updates["idioma"]:
        updates["idioma"] = updates["idioma"].lower()

    if "password" in updates:
        password = updates.pop("password")
        if password:
            user.password_hash = hash_password(password)

    if "username" in updates and updates["username"]:
        existing_user = (
            db.query(User)
            .filter(User.username == updates["username"], User.id != user.id)
            .first()
        )
        if existing_user:
            raise HTTPException(status_code=409, detail="Usuario ja existe")

    for field, value in updates.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/profile", response_model=UserResponse)
def update_own_profile(
    user_id: int,
    payload: UserUpdate,
    x_actor_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if x_actor_id != user_id:
        raise HTTPException(status_code=403, detail="Usuario pode editar apenas o proprio perfil")

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    updates = payload.model_dump(exclude_unset=True)

    for blocked_field in ("role", "is_active", "username"):
        updates.pop(blocked_field, None)

    if "pais_operacao" in updates and updates["pais_operacao"]:
        updates["pais_operacao"] = updates["pais_operacao"].upper()

    if "idioma" in updates and updates["idioma"]:
        updates["idioma"] = updates["idioma"].lower()

    if "password" in updates:
        password = updates.pop("password")
        if password:
            user.password_hash = hash_password(password)

    for field, value in updates.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    x_actor_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
):
    actor = None

    if x_actor_id is not None:
        actor = db.query(User).filter(User.id == x_actor_id, User.is_active.is_(True)).first()

    if not actor or actor.role != "ROOT":
        raise HTTPException(status_code=403, detail="Somente root pode excluir usuario")

    if actor.id == user_id:
        raise HTTPException(status_code=400, detail="Root nao pode excluir a propria conta")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    user.is_active = False
    db.commit()

    return {
        "deleted": True,
        "mode": "deactivated",
        "user_id": user_id,
    }


@router.post("/assign-leads")
def assign_leads(
    payload: AssignLeadsRequest,
    db: Session = Depends(get_db),
    _: User | None = Depends(require_admin_actor),
):
    broker = (
        db.query(User)
        .filter(User.id == payload.broker_id, User.role == "BROKER", User.is_active.is_(True))
        .first()
    )

    if not broker:
        raise HTTPException(status_code=404, detail="Broker ativo nao encontrado")

    query = db.query(Lead).filter(Lead.assigned_to_user_id.is_(None))

    if payload.nicho:
        query = query.filter(Lead.nicho == payload.nicho.upper())

    if payload.pais:
        query = query.filter(Lead.pais == payload.pais.upper())

    leads = query.order_by(Lead.score.desc().nullslast(), Lead.id).limit(payload.limit).all()

    for lead in leads:
        lead.assigned_to_user_id = broker.id
        lead.pipeline = "NOVO LEAD"

    db.commit()

    return {
        "broker_id": broker.id,
        "broker": broker.username,
        "leads_enviados": len(leads),
    }


@router.post("/return-leads-to-bank")
def return_leads_to_bank(
    payload: ReturnLeadsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_root_actor),
):
    if not payload.all and (payload.limit is None or payload.limit < 1):
        raise HTTPException(status_code=400, detail="Informe uma quantidade ou marque todos")

    query = db.query(Lead).filter(Lead.assigned_to_user_id.isnot(None))

    if payload.broker_id:
        query = query.filter(Lead.assigned_to_user_id == payload.broker_id)

    if payload.nicho:
        query = query.filter(Lead.nicho == payload.nicho.upper())

    if payload.pais:
        query = query.filter(Lead.pais == payload.pais.upper())

    query = query.order_by(Lead.id)

    if not payload.all:
        query = query.limit(payload.limit)

    leads = query.all()

    for lead in leads:
        lead.assigned_to_user_id = None
        lead.pipeline = "NOVO LEAD"

    db.commit()

    return {
        "leads_devolvidos": len(leads),
        "broker_id": payload.broker_id,
        "todos": payload.all,
    }
