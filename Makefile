.PHONY: refresh run

PYTHON ?= python3
RAW_DIR ?= data/raw

refresh:
	$(PYTHON) scripts/preprocess_corpus.py --raw-dir $(RAW_DIR)

run:
	streamlit run app.py
