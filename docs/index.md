# Niramaya-AI engineering manual

This documentation describes the repository as inspected on 2026-10-15. It distinguishes code-level behavior from deployment or live-service verification. **Implemented** means the code path exists; **verified** means a named test or live check exercised it. Unit tests use SQLite and fake storage and do not prove cloud behavior.

## Start here

| Reader | Start with |
| --- | --- |
| New developer | [Overview](01-project-overview.md), [repository guide](05-repository-and-module-guide.md), [local development](development.md) |
| API/frontend developer | [System architecture](03-system-architecture.md), [API inventory](reference/endpoint-inventory.md), [frontend architecture](06-frontend-architecture.md) |
| Backend/data engineer | [Backend architecture](07-backend-architecture.md), [database schema](10-database-schema.md), [migrations](11-database-migrations.md) |
| Medical-data engineer | [Processing pipeline](13-document-processing-pipeline.md), [extraction rules](14-medical-data-extraction-rules.md), [state machine](15-document-state-machine.md) |
| Retrieval/ML engineer | [Chunking and embeddings](16-chunking-and-embeddings.md), [Qdrant](17-qdrant-vector-database.md), [RAG](18-rag-retrieval-and-generation.md) |
| Security/reviewer | [Security and privacy](21-security-and-privacy.md), [threat model](35-threat-model.md), [verification matrix](reference/verification-matrix.md) |
| Operator | [Deployment](deployment.md), [release checklist](release-checklist.md), [operational runbooks](36-operational-runbooks.md), [limitations](32-known-limitations-and-roadmap.md) |

## Documentation map

1. [Project overview](01-project-overview.md) and [requirements and scope](02-requirements-and-scope.md)
2. [System architecture](03-system-architecture.md), [architecture decisions](04-architecture-decisions.md) and [individual ADRs](decisions/README.md), [module guide](05-repository-and-module-guide.md)
3. [Frontend](06-frontend-architecture.md) and [backend](07-backend-architecture.md)
4. [API reference](08-api-reference.md), [authentication and authorization](09-authentication-and-authorization.md)
5. [Database schema](10-database-schema.md), [migration history and procedure](11-database-migrations.md)
6. [Private file storage](12-file-storage-and-s3.md), [document processing](13-document-processing-pipeline.md), [extraction rules](14-medical-data-extraction-rules.md), [state machine](15-document-state-machine.md)
7. [Chunking and embeddings](16-chunking-and-embeddings.md), [Qdrant](17-qdrant-vector-database.md), [retrieval and generation](18-rag-retrieval-and-generation.md), [AI integrations](19-ai-models-and-integrations.md)
8. [Business rules](20-business-rules-and-validation.md), [security](21-security-and-privacy.md), [errors and retries](22-error-handling-and-retries.md), [observability](23-logging-monitoring-and-health.md)
9. [Testing](24-testing-strategy.md), [development](development.md), [configuration](reference/configuration-reference.md), [deployment](deployment.md), [CI](28-ci-cd-and-github-workflows.md)
10. [Troubleshooting](29-troubleshooting-runbooks.md), [performance](30-performance-and-scalability.md), [backup/deletion](31-backup-recovery-and-deletion.md), [release checklist](release-checklist.md), [limitations](32-known-limitations-and-roadmap.md), [glossary](33-glossary.md)
11. [Data-flow catalogue](34-data-flow-catalog.md), [threat model](35-threat-model.md), [runbooks](36-operational-runbooks.md)

## Existing focused references

- [Frontend API integration](frontend/api-integration.md), [document workflow](frontend/document-workflow.md), [assistant security](frontend/assistant-security.md), [evidence presentation](frontend/citations-and-evidence.md)
- [Medical-data provenance](medical-data/data-provenance.md), [normalization](medical-data/normalization.md), [processing lifecycle](medical-data/document-processing.md)
- [Access control](security/access-control.md), [user-scoped retrieval](security/user-scoped-retrieval.md)
- [Chunking](ai/chunking-strategy.md), [embedding setup](ai/embedding-models.md), [Qdrant operations](ai/qdrant-operations.md), [RAG pipeline](ai/rag-pipeline.md)
- [Data-flow notes](architecture/data-flow.md), [data model notes](database/data-model.md), [worker runbook](operations/document-processing-runbook.md), [reindexing](operations/reindexing-and-recovery.md)
- [Frontend testing](frontend/testing.md), [processing tests](testing/document-processing-tests.md), [RAG tests](testing/rag-tests.md)

## Diagrams and generated inventories

Editable Mermaid sources live in [`diagrams/`](diagrams/). The `reference/` directory contains the environment-variable, endpoint, dependency, database-object, and verification inventories. These files are maintained against source; when they disagree with code, code and migrations are authoritative and the discrepancy should be corrected.

## Status vocabulary

- **Implemented and verified:** exercised by named tests or an explicitly described live check.
- **Implemented, not verified:** source path exists, but the behavior was not exercised in the stated environment.
- **Partially implemented:** only a subset of the end-to-end behavior exists.
- **Mocked/simulated:** test fixture or fake replaces a real integration.
- **Blocked:** infrastructure, credentials, or permission prevented verification.
- **Planned:** recommendation, not current behavior.

See the [verification matrix](reference/verification-matrix.md) and [known limitations](32-known-limitations-and-roadmap.md) before treating a feature as operational.
