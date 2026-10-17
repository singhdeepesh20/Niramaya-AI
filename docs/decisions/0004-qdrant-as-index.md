# ADR-0004: Qdrant as a rebuildable candidate index

- **Status:** Implemented; rationale reconstructed.
- **Context:** Semantic candidates complement lexical search, while database authorization must remain independent of vector payloads.
- **Decision observed:** Store vectors/metadata in Qdrant, canonical chunk text in PostgreSQL, apply server-owned owner filters, and re-resolve IDs through SQL before creating evidence.
- **Alternatives:** Not documented.
- **Consequences:** Semantic search is optional and rebuildable; external cleanup/configuration is another failure boundary. A missing collection can be created by current indexing code, so environment/permissions must be intentionally scoped.
