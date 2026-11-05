# Run Career Mate on your machine

Local development setup: PostgreSQL in Docker, the API with hot reload, the web UI with Vite. No login (one dev user) unless you connect a Supabase project. To host it for real users, see [DEPLOYMENT.md](DEPLOYMENT.md).

You need about 15 minutes.

## 1. Install the tools

| Tool | Why | Install |
|---|---|---|
| Git | get the code | https://git-scm.com/downloads |
| uv | Python and dependencies (it installs the right Python for you) | Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"`<br>macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 20+ | the web interface | https://nodejs.org |
| Docker Desktop | the local PostgreSQL database | https://docs.docker.com/get-docker/ |

## 2. Get the code and install dependencies

```bash
git clone https://github.com/ifatmagamha/Career-Mate.git
cd Career-Mate
uv sync --locked
npm --prefix ui install
```

`uv sync --locked` creates `.venv/` with the exact versions from `uv.lock` (Python 3.14, from `.python-version`).

## 3. Start the database

```bash
docker compose up -d db
```

This runs PostgreSQL 17 with the pgvector extension (the same one Supabase provides) on `localhost:5432`, with its data in a Docker volume (`pgdata`) that survives restarts. `docker compose down` stops it; `docker compose down -v` also **deletes** the data.

## 4. Create your instance

```bash
uv run python -m src.cli init
```

This creates `.env` (from `.env.example`, whose `DATABASE_URL` already points at the local database) and applies the database migrations. It is safe to run again: it never overwrites `.env`, and only applies migrations that have not run yet.

## 5. Add your API keys

Open `.env` and fill in:

| Variable | Used for | Where to get it | Cost |
|---|---|---|---|
| `HF_TOKEN` | reading offers, writing letters, "Ask" search (default model `openai/gpt-oss-120b` served by Groq) | https://huggingface.co/settings/tokens → **Fine-grained** → preset **Inference** | free with the Groq step below |
| `GEMINI_API_KEY` | meaning-based search (embeddings) | https://aistudio.google.com/apikey | free tier |

To make the Hugging Face calls free: create a key on https://console.groq.com, then paste it as Groq's **custom provider key** on https://huggingface.co/settings/inference-providers.

Then check everything, including one tiny request per model:

```bash
uv run python -m src.cli check --live
```

Every line should start with `[ok]` (`[..]` is a warning, e.g. "no login" in development). `[!!]` lines say what is missing.

## 6. Run it

Terminal 1, the API:

```bash
uv run uvicorn src.api.server:app --reload
```

Terminal 2, the web interface:

```bash
npm --prefix ui run dev
```

Open http://localhost:5173. Start with **Profile → upload your CV**, then **Job Explorer → paste a job link** or **Add offer**.

### Optional: test the login locally

Create a free Supabase project (see [DEPLOYMENT.md](DEPLOYMENT.md), step 1), then:

- in `.env`: `SUPABASE_URL=https://<project>.supabase.co`
- in `ui/.env.local`: `VITE_SUPABASE_URL=https://<project>.supabase.co` and `VITE_SUPABASE_ANON_KEY=<publishable key>`

Restart both. The UI now shows a sign-in page and the API rejects requests without a valid token. The database stays local.

### Optional: run the API as a container (like production)

```bash
docker compose up --build
```

Builds the image from the `Dockerfile`, applies migrations and serves the API on `localhost:8000` (stop the `uv run uvicorn` one first).

## 7. Already used the SQLite version?

Your old offers, folders, views, contacts and CV profile are in `data/career_mate.db` and `data/profile.json`. Copy them into PostgreSQL for a user:

```bash
uv run python -m src.cli import-sqlite --user 00000000-0000-0000-0000-000000000001
```

That id is the local dev user. For a Supabase user, use their id from **Authentication → Users**, and point `DATABASE_URL` at that database. Re-running skips offers already imported. The old files are not modified; delete them once you have checked the result.

## 8. Customize your copy

| You want to… | Edit |
|---|---|
| Use another model for everything | `[defaults]` in `config/models.toml` |
| Use another model for one task (letters, extraction…) | add `provider` / `model` to that role in `config/models.toml` |
| Try a model without editing files | `LLM_DEFAULT_MODEL=…` or `LLM_EXTRACT_MODEL=…` in `.env` |
| Add a provider (Ollama, vLLM, OpenRouter…) | a `[providers.<name>]` block in `config/models.toml` (any OpenAI-compatible API) |
| Run the API on another port | `uvicorn … --port 8010`, and create `ui/.env.local` with `VITE_API_URL=http://localhost:8010` |
| Merge skill spellings ("postgres" → "PostgreSQL") | `SKILL_ALIASES` in `src/storage/db.py` |
| Change statuses or contract types | `STATUSES` in `src/storage/db.py`, the `Sheet…` lists in `src/schemas/job_offer.py` |
| Change how offers are read or letters written | `EXTRACT_PROMPT` in `src/agents/capture.py`, prompts in `src/prompts/` |
| Make a new field filterable (dropdown, saved views, "Ask") | `ENUM_FILTERS` in `src/storage/db.py` |
| Change the database schema | add a new numbered file in `src/storage/migrations/` (never edit one that already ran), then `uv run python -m src.cli migrate` |
| Tune meaning-based search after changing the embedding model | run `uv run python scripts/measure_search.py`, then set `min_similarity` / `similarity_margin` in `[roles.embed]` |
| Check the "Ask" search after changing its model or prompt | `uv run python scripts/measure_query.py` |

Run `uv run python -m src.cli check --live` after changing models.

## 9. Update to a new version

```bash
git pull
uv sync --locked
npm --prefix ui install
uv run python -m src.cli migrate
```

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `check` shows `cannot connect` | start the database (`docker compose up -d db`) and check `DATABASE_URL` |
| `check` shows pending migrations | `uv run python -m src.cli migrate` |
| `check` shows `[!!] … needs an API key` | set that variable in `.env` |
| "Error connecting to server" in the web interface | start the API (step 6), or fix `VITE_API_URL` |
| The UI keeps returning to the sign-in page | the API has a different `SUPABASE_URL` than the UI's `VITE_SUPABASE_URL` |
| HTTP 429 / rate limit in the logs | free-tier per-minute limit: the app waits and retries; for heavy use switch model in `config/models.toml` |
| Port 5432, 8000 or 5173 already in use | another Postgres/copy is running; stop it or change the port |
