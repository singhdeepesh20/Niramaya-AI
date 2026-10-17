# Environment configuration

The authoritative inventory is [reference/configuration-reference.md](reference/configuration-reference.md), derived from `app/core/config.py` and frontend environment usage. Backend settings load case-sensitive values from the process environment or root `.env`; Pydantic Settings ignores unknown keys. `DATABASE_URL` and `JWT_SECRET_KEY` are required at import/startup. Provider secrets are optional, but the corresponding operation will be unavailable or use SDK credential discovery.

`.env.example` is a template only. Root `.env` and frontend `.env.local` must remain ignored and untracked. `frontend/.env.example` may contain only public build-time API URL settings; never place service credentials in `NEXT_PUBLIC_*` variables. Use a secret manager/IAM role in deployed environments. Changing settings in `.env` requires restarting API and worker processes because settings are cached at import.
