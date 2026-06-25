# QueueStorm Sort-Ticket Service

A small FastAPI service built for the **QueueStorm Warmup** mock preliminary of
the SUST CSE Carnival 2026 Codex Community Hackathon. It exposes two
endpoints:

- `GET /health` — service health probe.
- `POST /sort-ticket` — accepts a single CRM ticket and returns a structured
  classification (case type, severity, department, summary, review flag,
  confidence).

Classification is performed by an LLM accessed via the OpenAI-compatible
chat-completions API. The 5 public sample cases from the problem statement
are inlined as few-shot examples. A safety guard scrubs `agent_summary` so
the service never asks the customer to share their PIN, OTP, password, or
full card number.

## Endpoints

### `GET /health`

```bash
curl https://<your-host>/health
# {"status":"ok"}
```

### `POST /sort-ticket`

Request:

```json
{
  "ticket_id": "T-001",
  "channel": "app",
  "locale": "en",
  "message": "I sent 5000 taka to a wrong number this morning, please help me get it back"
}
```

Response:

```json
{
  "ticket_id": "T-001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT to a wrong number and requests recovery.",
  "human_review_required": true,
  "confidence": 0.85
}
```

`human_review_required` is forced to `true` whenever severity is `critical`
or case_type is `phishing_or_social_engineering`. Phishing tickets are also
always routed to the `fraud_risk` department.

## Environment variables

Secrets are loaded only from the environment. Copy `.env.example` to `.env`
for local development (the `.env` file is gitignored).

| Variable           | Required | Default                       | Description                                 |
| ------------------ | -------- | ----------------------------- | ------------------------------------------- |
| `LLM_API_KEY`      | Yes      | —                             | API key for the LLM provider.               |
| `LLM_BASE_URL`     | No       | `https://api.openai.com/v1`   | OpenAI-compatible base URL.                 |
| `LLM_MODEL`        | No       | `gpt-4o-mini`                 | Model name.                                 |
| `MAX_MESSAGE_BYTES`| No       | `4096`                        | Maximum size of the `message` field, in bytes. |

## Local development

```bash
python -m venv .venv
. .venv/Scripts/activate          # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env              # then fill in LLM_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run the test suite:

```bash
pytest -q
```

Tests stub out the LLM, so they pass without an API key.

## Deployment

See [`runbook.md`](./runbook.md) for full replicate-the-deployment steps.
The service is platform-agnostic and runs anywhere that can serve a
Python 3.11+ ASGI app over HTTPS. We use Render / Railway / Fly / EC2 /
Poridhi Lab, but any of them works.

## Security notes

- The LLM API key is read from the environment only and is never logged.
- The message body is capped (`MAX_MESSAGE_BYTES`, default 4 KB) and the
  request body is capped at the FastAPI layer.
- Error responses never echo the raw customer message.
- The safety guard scrubs the LLM-generated summary against PIN, OTP,
  password, CVV, and full card number requests. If the model ever returns
  a forbidden summary, it is replaced with a safe rewrite and the ticket
  is forced into `human_review_required = true`.
- Phishing tickets are always routed to `fraud_risk`, even if the model
  misclassifies the department.

## Known issues

- If the upstream LLM is unavailable, `/sort-ticket` returns HTTP 502.
  No request is retried automatically; the client should decide.
- The classifier is single-shot; we do not currently chain multiple LLM
  calls or fall back to a rules-based path.
