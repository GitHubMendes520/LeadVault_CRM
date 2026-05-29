import argparse
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.database.connection import Base, engine, SessionLocal
from app.models.lead import Lead
from app.models.user import User

DEFAULT_SOURCE_DB = Path("/Users/user/Desktop/LeadVault_Matrix/banco/leadvault.db")
BATCH_SIZE = 1000


def clean_text(value):
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def clean_score(value):
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def lead_key(lead):
    site = lead.get("site")
    email = lead.get("email")

    if not site and not email:
        return None

    return ((site or "").lower(), (email or "").lower())


def iter_source_leads(source_db):
    query = """
        SELECT
            nome,
            contato,
            email,
            site,
            endereco,
            nicho,
            pais,
            score
        FROM dados_segmentados
        WHERE COALESCE(TRIM(nome), '') <> ''
           OR COALESCE(TRIM(email), '') <> ''
           OR COALESCE(TRIM(site), '') <> ''
    """

    with sqlite3.connect(source_db) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute(query):
            yield {
                "nome": clean_text(row["nome"]),
                "contato": clean_text(row["contato"]),
                "email": clean_text(row["email"]),
                "site": clean_text(row["site"]),
                "endereco": clean_text(row["endereco"]),
                "nicho": clean_text(row["nicho"]),
                "pais": clean_text(row["pais"]),
                "score": clean_score(row["score"]),
                "pipeline": "NOVO LEAD",
            }


def flush_batch(session, batch):
    if not batch:
        return 0

    session.bulk_insert_mappings(Lead, batch)
    session.commit()
    return len(batch)


def import_leads(source_db):
    Base.metadata.create_all(bind=engine)

    total_read = 0
    total_inserted = 0
    batch = []

    with SessionLocal() as session:
        existing_keys = {
            ((site or "").lower(), (email or "").lower())
            for site, email in session.query(Lead.site, Lead.email).all()
            if site or email
        }

        for lead in iter_source_leads(source_db):
            total_read += 1
            key = lead_key(lead)

            if key and key in existing_keys:
                continue

            if key:
                existing_keys.add(key)

            batch.append(lead)

            if len(batch) >= BATCH_SIZE:
                total_inserted += flush_batch(session, batch)
                batch.clear()

        total_inserted += flush_batch(session, batch)

    return total_read, total_inserted


def main():
    parser = argparse.ArgumentParser(
        description="Importa leads do LeadVault_Matrix para o PostgreSQL do LeadVault CRM."
    )
    parser.add_argument(
        "--source-db",
        default=DEFAULT_SOURCE_DB,
        type=Path,
        help="Caminho para o SQLite leadvault.db do LeadVault_Matrix.",
    )
    args = parser.parse_args()

    if not args.source_db.exists():
        raise FileNotFoundError(f"Banco de origem nao encontrado: {args.source_db}")

    total_read, total_inserted = import_leads(args.source_db)
    print(f"Lidos do Matrix: {total_read}")
    print(f"Inseridos no CRM: {total_inserted}")


if __name__ == "__main__":
    main()
