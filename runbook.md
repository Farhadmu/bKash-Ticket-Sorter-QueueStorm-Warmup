# Runbook — Replicating the Deployment on Render

This runbook lets the grader (or a teammate) bring up the service from a
clean clone on **Render**, in under 10 minutes.

## 1. Prerequisites

- Python 3.11 or newer (`python --version`).
- `pip` and `venv` available.
- A network egress to the LLM provider (`LLM_BASE_URL`).
- An LLM API key. The default expects an OpenAI-compatible endpoint
  (e.g. `https://api.openai.com/v1`).

## 2. Clone and install

```bash
git clone <your-repo-url> queuestorm-sort-ticket
cd queuestorm-sort-ticket
python -m venv .venv
. .venv/Scripts/Activate.ps1   # PowerShell; on bash use: source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configure secrets

Create a local `.env` file (gitignored) from the template:

```bash
cp .env.example .env
```

Fill in at minimum:

```
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

`LLM_API_KEY` is the only required value. The defaults for `LLM_BASE_URL`,
`LLM_MODEL`, and `MAX_MESSAGE_BYTES` are fine for a standard OpenAI key.

## 4. Run locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/sort-ticket \
  -H "content-type: application/json" \
  -d "{\"ticket_id\":\"T-LOCAL\",\"message\":\"I sent 3000 to wrong number\"}"
```

## 5. Run the test suite

The tests stub out the LLM, so they pass without an API key.

```bash
pytest -q
```

Expected: all tests pass. The suite covers the 5 public sample cases, the
safety rule, schema validation, and phishing routing.

## 6. Deploy to Render

1. Push the repo to GitHub (do **not** commit `.env`).
2. In Render, create a new **Web Service** from the repo.
3. Build command: `pip install -r requirements.txt`.
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
5. Set environment variables on the service:
   - `LLM_API_KEY` (Secret)
   - `LLM_BASE_URL` (optional)
   - `LLM_MODEL` (optional)
6. Wait for the deploy to finish. Render provisions HTTPS automatically.

> **Note:** `runtime.txt` pins Python to **3.12.7**. Render's default
> (currently Python 3.14) does not yet have prebuilt wheels for our
> pinned `pydantic-core`, which would force a Rust/maturin build and
> fail on Render's read-only filesystem.

7. Smoke-test:

```bash
curl https://<your-render-host>/health
curl -X POST https://<your-render-host>/sort-ticket \
  -H "content-type: application/json" \
  -d "{\"ticket_id\":\"T-LIVE\",\"message\":\"Someone called asking my OTP, is that bKash?\"}"
```

The second call should return `case_type=phishing_or_social_engineering`,
`severity=critical`, `department=fraud_risk`, and
`human_review_required=true`.

## 7. What to submit

When filling the Google Form, use:

- **Team name**: your registered team name.
- **GitHub repository URL**: the public repo, including this README and
  the `runbook.md`.
- **Live API base URL**: the HTTPS URL of the deployed service
  (e.g. `https://queuestorm-sort-ticket.onrender.com`).
- **Deployment platform**: Render.
- **LLM used**: yes / no and which model.
- **Known issues or blockers**: optional, but appreciated.

## 8. Troubleshooting

- **`LLM_API_KEY is not set`** — the service refuses to start without
  the key. Set it in the host's environment or in a local `.env` file.
- **`HTTP 502 Classification unavailable`** — the LLM provider returned
  an error. Check `LLM_BASE_URL`, the model name, and the key's quota.
- **`HTTP 413 Message too long`** — the message exceeded
  `MAX_MESSAGE_BYTES`. Raise the env var, or split the ticket.
- **Test failures** — run `pytest -q` locally to see details. The
  classifier is stubbed in tests, so a failure points at the safety
  guard, schema, or routing logic rather than the LLM.
