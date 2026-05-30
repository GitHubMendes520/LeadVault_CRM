import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.security import hash_password
from app.database.connection import Base, SessionLocal, engine
from app.models import lead, support_ticket, user
from app.models.user import User
from app.routes.lead_routes import router as lead_router
from app.routes.support_routes import router as support_router
from app.routes.user_routes import router as user_router

app = FastAPI(
    title="LeadVault CRM MVP",
    version="1.0.0"
)

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


@app.on_event("startup")
def create_database_tables():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS valor_negocio NUMERIC(12, 2) DEFAULT 0"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS pais_operacao VARCHAR DEFAULT 'BR'"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS idioma VARCHAR DEFAULT 'pt'"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP"))
        db.commit()

        if db.query(User).count() == 0:
            root_user = User(
                username=os.getenv("ROOT_USERNAME", "root"),
                password_hash=hash_password(os.getenv("ROOT_PASSWORD", "12345m*")),
                role="ROOT",
                full_name=os.getenv("ROOT_FULL_NAME", "Administrador LeadVault"),
                is_active=True,
            )
            db.add(root_user)
            db.commit()
    finally:
        db.close()


@app.get("/")
def home():
    frontend_index = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
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
