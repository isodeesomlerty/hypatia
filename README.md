# Hypatia

Hypatia turns a body of research into a living map of claims, evidence, and contradictions.

Instead of reading papers one by one and manually stitching together where the literature agrees, conflicts, or narrows a result, Hypatia extracts substantive claims, assesses methodological health, and maps paper relationships in an interactive research graph. It is designed to make the research landscape legible at a glance and explorable in depth.

**Live demo:** [hypatia.streamlit.app](https://hypatia.streamlit.app/)

**Display note:** For the best visual experience, open the app in light mode.

## Why Hypatia

One of the biggest bottlenecks in scientific discovery sits upstream of any single breakthrough: the literature itself. On important questions, there are too many papers, too many conflicting conclusions, and too many methodological differences buried in details that few people have time to untangle. Hypatia is an attempt to make that research landscape visible, so users can move from isolated papers to a clearer view of the field as a whole. The name is a nod to Hypatia of Alexandria: a symbol of scholarship, inquiry, and the pursuit of knowledge across disciplines.

## What It Does

- Extracts substantive claims from academic papers
- Evaluates methodological health and surfaces caution flags
- Compares papers and identifies supports, contradictions, qualifications, and extensions
- Maps the corpus as an interactive research map
- Supports natural-language search across the research map

## Try It

The fastest way to experience Hypatia is through the live app:

- [Live demo](https://hypatia.streamlit.app/)
- Use light mode for the intended visual presentation
- Upload academic papers in PDF form to build the research map
- Explore the graph as papers are added, then click papers or paper relationships to inspect claims, methodology, and cross-paper links

The hosted app is best treated as a public demo surface. You can open it immediately, but meaningful use depends on adding a corpus of academic PDFs. Some workflows depend on API-backed processing and may be constrained by deployment settings or Anthropic rate limits.

## Run Locally

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

5. Launch the app:

```bash
streamlit run app.py
```

Optional: if you already have cached paper JSON files and want to rebuild registrations, missing pairwise relationships, and graph snapshots:

```bash
make refresh
```

## How It Works

- A Streamlit frontend renders the research map, search flow, and paper / relationship detail panels.
- A Claude-first pipeline analyzes PDFs, extracts claims, scores methodological health, and compares papers pairwise.
- Cached paper and relationship artifacts are stored locally as JSON so the graph can be rebuilt incrementally and explored without reprocessing everything on each run.

## Current Limitations

- Dark mode is not visually tuned yet; the app is designed for light mode.
- Hosted deployments may rely on a smaller or demo corpus unless data is explicitly bundled or loaded externally.
- LLM-backed ingestion, search, and pairwise comparison depend on Anthropic availability, deployment secrets, and API limits.

## Roadmap

- Stronger hosted deployment and persistent corpus support
- Better export and report-generation workflows
- Larger-scale corpus ingestion and management
- Richer paper-relationship explanation and graph filtering
- An agentic replication engine that attempts to reproduce, stress-test, or challenge the claims made by papers
- Researcher-facing collaboration and review features

Built during the Anthropic hackathon and continued as an ongoing research-intelligence project.
