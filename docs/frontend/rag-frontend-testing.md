# RAG frontend checks

The frontend package currently provides ESLint and Next.js production-build scripts. It does not include a component-test runner or browser automation dependency, so component and keyboard interaction tests are not currently executable in this repository without adding a test framework.

Run the available checks from `frontend/`:

```bash
npm run lint
npm run build
```

The Python backend tests cover the authenticated `/api/v1/health/ask` contract, owner-scoped retrieval, citation construction, and evidence-only behavior:

```bash
python -m pytest -q
```

The assistant's manual integration path is: sign in, open **Medical records assistant**, select an indexed report if desired, ask a question, inspect any returned evidence/citations, and open the citation's protected document detail page. API failures should leave the question in the composer and show a retryable error; they must not produce a placeholder answer.
