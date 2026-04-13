PYTHON ?= .venv/bin/python3
NPM ?= npm
V2_DATABASE_URL ?= postgresql://hypatia:hypatia@127.0.0.1:5432/hypatia

.PHONY: preprocess refresh run v2-db-up v2-db-down v2-db-init v2-api v2-web v2-worker

preprocess:
	$(PYTHON) scripts/preprocess_corpus.py

refresh:
	$(PYTHON) scripts/refresh_cache.py

run:
	$(PYTHON) -m streamlit run app.py

v2-db-up:
	docker compose -f compose.v2.yml up -d postgres

v2-db-down:
	docker compose -f compose.v2.yml down

v2-db-init:
	DATABASE_URL=$(V2_DATABASE_URL) $(PYTHON) services/api/scripts/init_db.py --seed-demo

v2-api:
	PYTHONPATH=services/api DATABASE_URL=$(V2_DATABASE_URL) HYPATIA_STORAGE_BACKEND=postgres HYPATIA_ALLOW_DEMO_FALLBACK=0 HYPATIA_ALLOW_DEV_AUTH=0 $(PYTHON) -m uvicorn app.main:app --app-dir services/api --reload

v2-web:
	HYPATIA_API_BASE_URL=http://127.0.0.1:8000 HYPATIA_ENABLE_DEMO_FALLBACK=0 $(NPM) run web:dev

v2-worker:
	DATABASE_URL=$(V2_DATABASE_URL) HYPATIA_UPLOAD_STORAGE_ROOT=data/v2-uploads $(PYTHON) services/worker/worker/main.py --poll
