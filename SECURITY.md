# Security Notes

## Secrets

- The LLM API key is read from the `LLM_API_KEY` environment variable
  only. It is never hard-coded, never logged, and never echoed in error
  responses.
- A `.env.example` is committed (with empty values); the real `.env`
  file is `.gitignore`d.
- Customer messages are never logged by the service. The `/sort-ticket`
  log line includes only the ticket id, classified enum values, and
  elapsed time — never the message text or the API key.

## Safety rule

Per the problem statement, `agent_summary` must never ask the customer
to share their PIN, OTP, password, CVV, or full card number. The
service enforces this in two layers:

1. The system prompt instructs the LLM not to produce such requests.
2. `app/safety.py` post-processes every generated summary:
   - If it contains a request for a forbidden secret, the summary is
     replaced with a safe rewrite.
   - If it merely mentions a sensitive token, the response is flagged
     with `human_review_required = true` so a human agent reads it
     before acting.

## Routing safety

Phishing tickets are always routed to `fraud_risk`, even if the LLM
returns a different department. `human_review_required` is forced to
`true` for any critical or phishing ticket.

## Transport

- HTTPS is enforced by the deployment platform (Render, Railway, Fly,
  Vercel, EC2, Poridhi Lab, or any other reverse proxy in front of the
  app). The application itself speaks plain HTTP to the upstream
  proxy, which is standard.

## Dependencies

- Dependencies are pinned in `requirements.txt`.
- `pip-audit` is recommended in CI for ongoing supply-chain checks.

## What to report

If you find a security issue, please open a private issue or contact
the team lead. Do not file a public bug with exploit details before a
fix is available.
