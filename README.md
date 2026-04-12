# Hypatia

Hypatia is a local-first Streamlit app for exploring academic papers as a paper-level knowledge graph. It extracts claims, grades methodological health, links papers that support or contradict each other, and supports natural-language search across the claim corpus.

## What This Repo Includes

- A Streamlit app with an interactive `vis-network` graph
- A Claude-first PDF ingestion pipeline with local PDF parsing fallback
- Incremental preprocessing and JSON cache generation
- Paper-level drilldown for methodology checks, claims, and cross-paper relationships
- Search with a Sonnet primary path and a deterministic local fallback

## Quick Start

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and add your Anthropic API key:

```bash
cp .env.example .env
```

3. Put source PDFs in `data/raw/`.

4. Preprocess the corpus:

```bash
python scripts/preprocess_corpus.py
```

If you already have cached paper JSONs in `data/cache/papers/` and want to register any orphaned ones,
compute the missing pairwise relationships, and rebuild the graph snapshots:

```bash
make refresh
```

5. Launch the app:

```bash
streamlit run app.py
```

## Notes

- The preprocessed cache is written to `data/cache/`.
- Live upload uses the same analysis path as offline preprocessing, but only for one paper at a time.
- Password-protected, oversized, or overly long PDFs are rejected with a clear error instead of being processed unreliably.
