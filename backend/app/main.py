import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import hash_password
from app.core.storage import UPLOADS_DIR
from app.auth.routes import router as auth_router
from app.database.connection import Base, SessionLocal, engine
from app.models import import_job, lead, lead_event, support_ticket, user, contract, contract_event
from app.models.user import User
from app.routes.import_routes import router as import_router
from app.routes.admin_routes import router as admin_router
from app.routes.lead_routes import router as lead_router
from app.routes.support_routes import router as support_router
from app.routes.user_routes import router as user_router
from app.routes.contract_routes import router as contract_router

app = FastAPI(
    title="LeadVault CRM MVP",
    version="1.0.0"
)

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lead_router)
app.include_router(user_router)
app.include_router(support_router)
app.include_router(import_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(contract_router)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir), name="assets")

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


def ensure_index(db, primary_sql: str, *, fallback_sql: str | None = None, label: str = ""):
    try:
        db.execute(text(primary_sql))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        if not fallback_sql:
            raise

        logger.warning("Falha ao criar indice %s. Aplicando fallback seguro. Motivo: %s", label or primary_sql, exc)
        db.execute(text(fallback_sql))
        db.commit()


@app.on_event("startup")
def create_database_tables():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS valor_negocio NUMERIC(12, 2) DEFAULT 0"))
        db.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS pipeline_updated_at TIMESTAMP"))
        db.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"))
        db.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP"))
        db.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS estado VARCHAR"))
        db.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS cidade VARCHAR"))
        db.execute(text("UPDATE leads SET pipeline_updated_at = COALESCE(pipeline_updated_at, updated_at, CURRENT_TIMESTAMP) WHERE pipeline_updated_at IS NULL"))
        db.execute(text("UPDATE leads SET created_at = COALESCE(created_at, pipeline_updated_at, CURRENT_TIMESTAMP) WHERE created_at IS NULL"))
        db.execute(text("UPDATE leads SET updated_at = COALESCE(updated_at, pipeline_updated_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS manager_id INTEGER"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS pais_operacao VARCHAR DEFAULT 'BR'"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS estado_operacao VARCHAR DEFAULT ''"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS cidade_operacao VARCHAR DEFAULT ''"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS idioma VARCHAR DEFAULT 'pt'"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo_url VARCHAR"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company VARCHAR"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT TRUE"))
        db.execute(text("ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'ACTIVE'"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR DEFAULT 'STARTER'"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_max_brokers INTEGER DEFAULT 1"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_max_leads INTEGER DEFAULT 100"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        db.execute(text("UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL"))
        db.execute(text("UPDATE users SET status = 'ACTIVE' WHERE status IS NULL OR status = ''"))
        db.execute(text("UPDATE users SET plan = 'STARTER' WHERE plan IS NULL OR plan = ''"))
        db.execute(text("UPDATE users SET plan_max_brokers = 1 WHERE plan_max_brokers IS NULL"))
        db.execute(text("UPDATE users SET plan_max_leads = 100 WHERE plan_max_leads IS NULL"))
        db.execute(text("UPDATE users SET registered_at = CURRENT_TIMESTAMP WHERE registered_at IS NULL"))
        db.commit()

        ensure_index(
            db,
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower ON users (LOWER(email)) WHERE email IS NOT NULL AND email <> ''",
            label="uq_users_email_lower",
        )
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_users_status ON users (status)")
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users (email_verification_token)")

        ensure_index(
            db,
            "CREATE INDEX IF NOT EXISTS idx_leads_email_lower ON leads (LOWER(email))",
            fallback_sql="CREATE INDEX IF NOT EXISTS idx_leads_email_lower_hash ON leads (md5(lower(coalesce(email, ''))))",
            label="idx_leads_email_lower",
        )
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_leads_contato ON leads (contato)")
        ensure_index(
            db,
            "CREATE INDEX IF NOT EXISTS idx_leads_site_lower ON leads (LOWER(site))",
            fallback_sql="CREATE INDEX IF NOT EXISTS idx_leads_site_lower_hash ON leads (md5(lower(coalesce(site, ''))))",
            label="idx_leads_site_lower",
        )
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_leads_nicho ON leads (nicho)")
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_leads_pais ON leads (pais)")
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_leads_estado ON leads (estado)")
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_leads_cidade ON leads (cidade)")
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_leads_pais_estado_cidade ON leads (pais, estado, cidade)")
        ensure_index(db, "CREATE INDEX IF NOT EXISTS idx_leads_assigned_pipeline ON leads (assigned_to_user_id, pipeline)")

        if db.query(User).count() == 0:
            root_user = User(
                username=os.getenv("ROOT_USERNAME", "root"),
                password_hash=hash_password(os.getenv("ROOT_PASSWORD", "12345m*")),
                role="ROOT",
                full_name=os.getenv("ROOT_FULL_NAME", "Administrador LeadVault"),
                is_active=True,
                email_verified=True,
                status="ACTIVE",
                plan="ENTERPRISE",
            )
            db.add(root_user)
            db.commit()
    finally:
        db.close()


@app.get("/")
def home():
    frontend_index = frontend_dir / "index.html"
    if frontend_index.exists():
        return FileResponse(frontend_index)

    return {
        "status": "online",
        "sistema": "LeadVault CRM MVP",
        "mensagem": "CRM iniciado com sucesso"
    }


@app.get("/health")
def health():
    return {"status": "online"}
