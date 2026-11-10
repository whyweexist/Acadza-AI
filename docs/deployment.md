# Deployment plan (not executed)

## Frontend: Vercel / compatible Next.js host

Set root directory to `apps/web`. Set `API_BASE_URL` to the URL of the Python API. Set `REVIEW_TOKEN` as a **server-only** secret if enabling authenticated writes. For read-only public evaluation, omit `REVIEW_TOKEN`: the app shows actual precomputed sample cases, questions, MathML, diffs and replies even if backend is offline.

## SQLite API: one persistent worker

Run the FastAPI service on a persistent host with a mounted volume (e.g. a single Docker/Fly.io machine with a volume, Render persistent disk when available, or a small VM). Install from `services/triage/requirements.txt`, mount a persistent directory, set `SQLITE_PATH` to an absolute path in the mounted volume and run:

```bash
cd services/triage
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Set `ADMIN_REVIEW_TOKEN`, `CORS_ORIGINS`, and optional AI variables. Expose HTTPS. Use one API worker per SQLite file and explicit daily backups; reads can scale separately through cached snapshot endpoints, but do **not** blindly scale independent SQLite writers.

No model key is required for the precomputed console. For live AI triage, configure API key and models and run the batch command explicitly.

## Before publishing a writable demo

- Set long, unpredictable secrets on both server runtimes.
- Confirm proxy auth and server-to-server TLS.
- Restrict public mutation access; replace shared credentials with SSO before production use.
- Run `scripts/validate_results.py`, pytest, TypeScript typecheck, production build and browser workflow checks (not run here).
- Inspect visible question rendering and audit persistence.
- Confirm SQLite volume survives restarts, and test a restore from a backup.
- Rotate credentials after the seven-day demo.
- Record the actual live URL and video link only once created.

### Gemini / OpenRouter settings

Set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY`, or `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY`, in the **API container/server environment**. Use `LLM_CHEAP_MODEL` / `LLM_STRONG_MODEL` to select available model IDs. Never use `NEXT_PUBLIC_` for credentials. The UI key-entry mode only holds secrets in FastAPI's memory and is not appropriate for publicly accessible, unauthenticated demo pages. The Next.js proxy requires a faculty-entered token, validated by FastAPI. Restrict the web console and the backend's review endpoints to authorized staff in deployed environments.

Provider settings are not synchronized across multiple FastAPI worker processes. For production use env-injected secrets, a single control plane and durable verification workers. Demo jobs are not restart-durable and are marked interrupted on API restart; this avoids falsely displaying completion.
