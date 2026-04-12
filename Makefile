PYTHON ?= .venv/bin/python3

.PHONY: preprocess refresh run

preprocess:
	$(PYTHON) scripts/preprocess_corpus.py

refresh:
	$(PYTHON) scripts/refresh_cache.py

run:
	$(PYTHON) -m streamlit run app.py
