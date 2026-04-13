# Hypatia V2 Production Branch

This branch is where Hypatia grows from a Streamlit prototype into a durable
product architecture.

## Goals

- Keep `main` stable for the live Streamlit deployment.
- Build a production-ready web application without disrupting the prototype.
- Preserve Python for ingestion, comparison, search, and future replication
  workflows.
- Add the missing product layers: auth, database-backed workspaces, background
  jobs, and bulk corpus ingestion.

## Current structure

### `apps/web`

The new product-facing frontend. This will become the authenticated shell for:

- private workspaces
- batch PDF and ZIP uploads
- graph exploration
- paper and paper-relationship review
- job progress and retry visibility

### `services/api`

The Python API service. This will own:

- workspace-aware read and write endpoints
- auth verification
- graph, paper, relationship, and search payloads
- job creation and status retrieval

### `services/worker`

The Python background worker. This will own:

- paper ingestion
- claim extraction
- pairwise comparison
- graph rebuilds
- future replication-engine tasks

## Near-term milestones

1. Add auth and workspace identity to the web and API layers.
2. Introduce Postgres models for workspaces, papers, claims, relationships, and jobs.
3. Add object-storage-backed upload ingestion for PDFs and ZIPs.
4. Move pairwise comparison into durable background jobs.
5. Recreate the current graph and knowledge-panel flows against API data.

## Current API scaffold

The production API now exposes the first batch-ingestion-facing contracts:

- `GET /v1/viewer`
- `GET /v1/workspaces/{workspace_id}`
- `GET /v1/workspaces/{workspace_id}/graph`
- `GET /v1/workspaces/{workspace_id}/papers`
- `GET /v1/workspaces/{workspace_id}/jobs`
- `GET /v1/workspaces/{workspace_id}/batches`
- `POST /v1/uploads/batch`
- `POST /v1/uploads/batch-files`
- `GET /v1/uploads/batch/{batch_id}`
- `GET /v1/jobs/{job_id}`

These are still backed by an in-memory demo store for now, but the contract
shape is aligned with the eventual Postgres + object storage + worker design.

The V2 web workspace now consumes those API contracts through a typed
TypeScript fetch layer, with a demo fallback so the shell still renders even
before the real API and database are fully wired.

For auth, the branch now has a viewer-aware contract end to end:

- the Next.js app forwards a viewer context through request headers
- the FastAPI service resolves that into a `ViewerSummary`
- workspace reads are scoped to accessible workspaces only

This is still a development-mode bridge, but it gives us the same request shape
we will need when Clerk tokens replace the header fallback.

Clerk is now the intended real auth path for V2:

- the Next.js app can run behind `@clerk/nextjs`
- workspace pages can be protected through Clerk middleware
- the API can verify Clerk bearer tokens through the configured JWKS endpoint
- development header auth remains optional and should be disabled for strict local stack testing

## Storage backends

The API now chooses its storage backend through configuration:

- `HYPATIA_STORAGE_BACKEND=memory` forces the in-memory demo repository
- `HYPATIA_STORAGE_BACKEND=postgres` forces the Postgres repository
- `HYPATIA_STORAGE_BACKEND=auto` uses Postgres when `DATABASE_URL` is set and
  reachable, otherwise falls back to the in-memory repository

Fallback behavior is controlled by `HYPATIA_ALLOW_DEMO_FALLBACK`.

The first Postgres schema lives at:

- `services/api/app/schema.sql`

That schema covers:

- users
- workspaces
- workspace memberships
- papers
- paper relationships
- jobs
- upload batches and upload batch items
- claims and claim relationships

## Local development bootstrap

The quickest way to run the first durable V2 stack locally is:

1. Install the new Python and web dependencies:
   - `python3 -m pip install -e services/api -e services/worker`
   - `npm install`
2. Start local Postgres:
   - `make v2-db-up`
3. Apply the schema and seed the demo workspace:
   - `make v2-db-init`
4. Start the API in Postgres mode:
   - `make v2-api`
5. Start the worker:
   - `make v2-worker`
6. Start the web app:
   - `make v2-web`

Supporting files:

- `compose.v2.yml` starts the local Postgres container
- `services/api/scripts/init_db.py` applies `schema.sql`
- `services/api/.env.example`, `services/worker/.env.example`, and `apps/web/.env.example` show the expected local environment variables
- accepted uploaded files are stored under `data/v2-uploads/` by the local upload storage backend

The worker now processes queued `batch_ingestion` jobs by:

- reading accepted files from local upload storage
- creating new `papers` rows automatically
- skipping duplicate PDFs within the same workspace using file hashes
- creating pending paper-relationship edges for newly ingested papers until real pairwise comparison is implemented

For strict local stack testing, use:

- `HYPATIA_ALLOW_DEMO_FALLBACK=0`
- `HYPATIA_ALLOW_DEV_AUTH=0`
- `HYPATIA_ENABLE_DEMO_FALLBACK=0`

When Clerk is enabled in the web app, configure:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `CLERK_JWT_TEMPLATE`

And on the API side configure:

- `CLERK_ISSUER`
- `CLERK_JWKS_URL` if you do not want it derived from the issuer automatically

For local development, the seeded demo data is intentional: it lets the V2 web
shell render against Postgres immediately while the true upload and worker paths
are still being wired.

## Working rule

Nothing in this branch should assume the Streamlit prototype is gone yet. V2
replaces `main` only once it reaches feature parity on the core research-map
flows and is stable enough to retire the prototype cleanly.
