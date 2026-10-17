# ADR-0003: Deterministic extraction before optional generation

- **Status:** Implemented; rationale reconstructed.
- **Context:** Persisted medical facts need provenance and should not depend on generated model output.
- **Decision observed:** Extract PDF text/tables locally, run explicit rules and unit conversions, preserve source/page/warnings, and keep Q&A in a distinct optional service.
- **Alternatives:** Not documented.
- **Consequences:** The process is auditable and independent from LLM availability, but has finite coverage and is not clinically validated. New rules need synthetic tests and versioned provenance.
