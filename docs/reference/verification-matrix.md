# Verification matrix

Evidence recorded for the documentation task on 2026-10-15. “Pass” below describes the named local check only, not production deployment.

| Feature/check | Command/test | Environment | Result and limit |
| --- | --- | --- | --- |
| Python syntax | `python -m compileall -q app tests` | Local workspace | PASS; syntax/import compilation does not call application integrations. |
| Backend tests | `python -m pytest -q` (`tests/conftest.py` blanks cloud variables) | Temporary SQLite, fake S3/vector/provider | PASS, 79 tests; not live PostgreSQL RLS or cloud verification. |
| Auth and API | `tests/test_auth_api.py` | FastAPI TestClient + SQLite | PASS as part of suite; not production DB/identity provider. |
| Document processing | `tests/test_document_processing.py`, extraction/image tests | Synthetic files, fake S3, SQLite | PASS as part of suite; no actual patient reports or production OCR host. |
| Cross-user retrieval | `tests/test_health_isolation.py` | SQLite/fake Qdrant response | PASS as part of suite; SQL owner revalidation/filter logic tested, not live Qdrant isolation. |
| Indexing | `tests/test_rag_indexing.py` | Fake embedding/Qdrant clients | PASS as part of suite; does not establish actual model weights/collection. |
| Frontend lint | `npm run lint` in `frontend/` | Local Node toolchain | PASS; not browser workflow validation. |
| TypeScript | `npx tsc --noEmit --incremental false` | Local frontend | PASS; static type check. |
| Production build | `npm run build` | Next.js 15 local | PASS; build used local frontend env file, but this does not verify API reachability. |
| Markdown links/source references | Local Python path validation | Repository docs | PASS; all relative Markdown links and checked inline source paths resolve. |
| API inventory | AST comparison with router declarations | Backend route modules | PASS; all declared routes included; `/health` is listed separately. |
| Configuration inventory | AST comparison with `Settings` fields | `app/core/config.py` | PASS; all fields represented; public frontend URL noted separately. |
| Mermaid diagrams | No Mermaid CLI validator found in environment | Editable `.mmd` files | Syntax not machine-validated; diagrams reviewed as text. |
| Documentation secret scan | Manual pattern scan of current docs and examples | Repository docs/history | Current docs avoid credential values; one placeholder database URI candidate in `.env.example` is a clearly local template; a possible historical README JWT assignment is documented without value. |
| PostgreSQL live schema/RLS | No live migration in this task | Not tested | BLOCKED/NOT VERIFIED; do not infer from SQLite tests. |
| AWS STS/S3 | Not tested in this documentation task | Not tested | NOT VERIFIED; fake storage tests only. |
| Qdrant auth/collection/write | Not tested in this documentation task | Not tested | NOT VERIFIED; do not infer from fake client tests. |
| Groq live generation | Not tested in this documentation task | Not tested | NOT VERIFIED; mocked provider unit test only. |
| Local embedding model download/load | Model exercised through test fakes | Model availability environment-dependent | NOT VERIFIED for installed production weights/device. |
| Browser E2E/accessibility | No test command configured | Not run | NOT IMPLEMENTED. |

Only issue a current live-service PASS after recording a fresh, safe check against the intended isolated service and its environment. Never include secret values or patient content in evidence.
