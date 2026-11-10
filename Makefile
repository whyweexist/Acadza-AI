.PHONY: api web fixtures triage check-schemas test-api test-web
api:
	cd services/triage && uvicorn app.main:app --reload --port 8000
web:
	cd apps/web && npm run dev
fixtures:
	python scripts/make_precomputed.py
	python scripts/build_demo.py
triage:
	python services/triage/scripts/triage.py
check-schemas:
	python scripts/validate_results.py
test-api:
	cd services/triage && pytest -q
test-web:
	cd apps/web && npm run typecheck && npm run build
