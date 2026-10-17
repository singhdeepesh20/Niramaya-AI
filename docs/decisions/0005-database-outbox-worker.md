# ADR-0005: Database outbox and lease-based worker

- **Status:** Implemented; rationale reconstructed.
- **Context:** Upload and later processing must survive API process exit without an external broker.
- **Decision observed:** Commit document metadata and a processing job atomically in PostgreSQL; worker claims pending rows with locks, leases, attempts and stale-lease recovery.
- **Alternatives:** Not documented.
- **Consequences:** Avoids a broker but couples throughput to PostgreSQL polling/locking and requires separate worker supervision. Retryable side effects should remain idempotent.
