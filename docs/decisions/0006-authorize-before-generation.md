# ADR-0006: Authorize evidence before generation

- **Status:** Implemented; rationale reconstructed.
- **Context:** Documents may contain malicious instructions, and model prompts are not an authorization boundary.
- **Decision observed:** Derive owner from verified JWT, filter Qdrant server-side, re-fetch candidate chunk IDs under PostgreSQL owner/document/generation/state predicates, then construct bounded evidence and citations before calling the model.
- **Alternatives:** Prompt-only isolation is explicitly insufficient.
- **Consequences:** The model receives no unauthorized excerpts by design. Correctness depends on preserving SQL filters, RLS, query tests and server-side evidence construction as the code evolves.
