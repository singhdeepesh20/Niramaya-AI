"""Read-only checks for the schema produced by the Alembic migration chain."""

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


def main() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    if not url.drivername.startswith("postgresql"):
        raise SystemExit("Migration schema verification requires PostgreSQL")
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        required_tables = {
            "alembic_version",
            "users",
            "medical_documents",
            "medical_entities",
            "medical_document_chunks",
            "health_chat_messages",
            "document_processing_jobs",
            "document_processing_events",
            "document_stage_runs",
            "medical_document_pages",
            "medical_document_tables",
        }
        missing_tables = required_tables - tables
        if missing_tables:
            raise SystemExit(f"Required migrated tables are missing: {', '.join(sorted(missing_tables))}")

        required_indexes = {
            "ix_medical_documents_owner_created",
            "ix_medical_chunks_owner_document",
            "ix_health_chat_owner_created",
            "ix_doc_processing_jobs_claim",
        }
        indexes = {
            index["name"]
            for table in required_tables - {"alembic_version", "users"}
            for index in inspector.get_indexes(table)
        }
        missing_indexes = required_indexes - indexes
        if missing_indexes:
            raise SystemExit(f"Required migrated indexes are missing: {', '.join(sorted(missing_indexes))}")

        tenant_tables = {
            "medical_documents",
            "medical_entities",
            "medical_document_chunks",
            "health_chat_messages",
            "document_processing_events",
            "document_stage_runs",
        }
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                    "EXISTS (SELECT 1 FROM pg_policies p WHERE p.tablename = c.relname "
                    "AND p.schemaname = current_schema()) AS has_policy "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = current_schema() AND c.relname::text = ANY(:table_names)"
                ),
                {"table_names": list(tenant_tables)},
            ).mappings()
            policies = {row["relname"]: row for row in rows}
        invalid_rls = sorted(
            name
            for name in tenant_tables
            if name not in policies
            or not policies[name]["relrowsecurity"]
            or not policies[name]["relforcerowsecurity"]
            or not policies[name]["has_policy"]
        )
        if invalid_rls:
            raise SystemExit(f"Tenant row-level security is missing or incomplete: {', '.join(invalid_rls)}")

        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if revision != "0007_chat_generation_status":
            raise SystemExit("Database revision does not match expected head 0007_chat_generation_status")
        print("Migration schema verified: tables, indexes, tenant RLS and expected revision are present.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
