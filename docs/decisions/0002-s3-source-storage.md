# ADR-0002: S3 for source document bytes

- **Status:** Implemented; rationale reconstructed.
- **Context:** Source reports are larger binary objects with private owner-specific access.
- **Decision observed:** Store bytes in configured S3; store generated object key and metadata in PostgreSQL; provide short-lived presigned GET only after owner check.
- **Alternatives:** Not documented.
- **Consequences:** Object and relational transactions are not atomic. Upload compensation and deletion jobs handle partial failure, but orphan cleanup and bucket-policy verification remain operator responsibilities.
