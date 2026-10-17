# ADR-0001: PostgreSQL as canonical structured store

- **Status:** Accepted in current implementation; rationale reconstructed.
- **Context:** Accounts, medical metadata, extraction outputs, chat history and durable jobs require relational integrity and transactions.
- **Decision observed:** Async SQLAlchemy with PostgreSQL in deployment and Alembic migrations; user/document foreign keys, explicit owner filters and PostgreSQL RLS.
- **Alternatives:** Not present in repository history.
- **Consequences:** PostgreSQL is authoritative for text, state and owner authorization. Operators must verify roles, RLS policies, migrations and backups. SQLite tests do not validate these PostgreSQL-specific properties.
