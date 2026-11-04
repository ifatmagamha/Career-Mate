# Set up your own Career Mate

Career Mate runs as **one private copy per person**: your own database, CV, offers, contacts and API keys, on your own machine. Nothing is shared between copies, and there is no account to create.

You need about 15 minutes.

## 1. Install the tools

| Tool | Why | Install |
|---|---|---|
| Git | get the code | https://git-scm.com/downloads |
| uv | Python and dependencies (it installs the right Python for you) | Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"`<br>macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 20+ | the web interface | https://nodejs.org |

## 2. Get the code and install dependencies

```bash
git clone https://github.com/ifatmagamha/Career-Mate.git
cd Career-Mate
uv sync --locked
npm --prefix ui install
```

`uv sync --locked` creates `.venv/` with the exact versions from `uv.lock` (Python 3.14, from `.python-version`).

## 3. Create your instance

```bash
uv run python -m src.cli init
```

This creates `.env` (from `.env.example`), your data folder and your database. It is safe to run again: it never overwrites `.env` or existing data.

## 4. Add your API keys

Open `.env` and fill in:

| Variable | Used for | Where to get it | Cost |
|---|---|---|---|
| `HF_TOKEN` | reading offers, writing letters, chat (default model `openai/gpt-oss-120b` served by Groq) | https://huggingface.co/settings/tokens → **Fine-grained** → preset **Inference** | free with the Groq step below |
| `GEMINI_API_KEY` | searching your CV (embeddings) | https://aistudio.google.com/apikey | free tier |

To make the Hugging Face calls free: create a key on https://console.groq.com, then paste it as Groq's **custom provider key** on https://huggingface.co/settings/inference-providers. Requests are then billed by Groq's free tier instead of your Hugging Face account (free accounts have no credits).

Then check everything, including one tiny request per model:

```bash
uv run python -m src.cli check --live
```

Every line should start with `[ok]`. `[!!]` lines say what is missing.

## 5. Run it

Terminal 1, the API:

```bash
uv run uvicorn src.api.server:app --reload
```

Terminal 2, the web interface:

```bash
npm --prefix ui run dev
```

Open http://localhost:5173. Start with **Profile → upload your CV**, then **Job Explorer → paste a job link** or **Add offer**.

## 6. Customize your copy

| You want to… | Edit |
|---|---|
| Use another model for everything | `[defaults]` in `config/models.toml` |
| Use another model for one task (letters, extraction…) | add `provider` / `model` to that role in `config/models.toml` |
| Try a model without editing files | `LLM_DEFAULT_MODEL=…` or `LLM_EXTRACT_MODEL=…` in `.env` |
| Add a provider (Ollama, vLLM, OpenRouter…) | a `[providers.<name>]` block in `config/models.toml` (any OpenAI-compatible API) |
| Keep your data somewhere else (a backed-up folder) | `DATA_DIR=` in `.env`, absolute path allowed, then run `init` again |
| Run the API on another port | `uvicorn … --port 8010`, and create `ui/.env.local` with `VITE_API_URL=http://localhost:8010` |
| Merge skill spellings ("postgres" → "PostgreSQL") | `SKILL_ALIASES` in `src/storage/db.py` |
| Change statuses or contract types | `STATUSES` in `src/storage/db.py`, the `Sheet…` lists in `src/schemas/job_offer.py` |
| Change how offers are read or letters written | `EXTRACT_PROMPT` in `src/agents/capture.py`, prompts in `src/prompts/` |

Run `uv run python -m src.cli check --live` after changing models.

## 7. Your data and privacy

- **Everything personal lives in your data folder** (`DATA_DIR`, default `data/`): `career_mate.db` (offers, tracking, contacts), `cvs/`, `profile.json`, `faiss_index/`. These and `.env` are git-ignored: never force-add them (`git add -f`).
- **Back up** by copying the data folder while the app is stopped. The database is a single SQLite file.
- **One database per person.** Don't share your data folder: it contains your CV and other people's contact details.
- **The API has no login.** It listens only on your own machine (`127.0.0.1`). Don't start it with `--host 0.0.0.0` on a shared network.
- **Model providers see what you send.** When you upload a CV or capture an offer, the text goes to the configured models. Free tiers may log prompts. For full privacy, point the roles at a local model (`local` or `vllm` provider in `config/models.toml`).

## 8. Update to a new version

```bash
git pull
uv sync --locked
npm --prefix ui install
uv run python -m src.cli init
```

`init` applies database upgrades and keeps your data.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `check` shows `[!!] … needs an API key` | set that variable in `.env` |
| "Error connecting to server" in the web interface | start the API (step 5), or fix `VITE_API_URL` |
| HTTP 429 / rate limit in the logs | free-tier per-minute limit: the app waits and retries; for heavy use switch model in `config/models.toml` |
| "index built with X, embed role is Y" | you changed the embedding model: upload your CV again to rebuild the index |
| Port 8000 or 5173 already in use | another copy is running, or use another port (section 6) |
