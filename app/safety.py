"""Safety guard for ``agent_summary``.

The problem statement explicitly forbids responses that ask the customer to
share their PIN, OTP, password, or full card number. This module scrubs the
LLM-generated summary and flags the ticket for human review whenever such a
request is detected.
"""
from __future__ import annotations

import re

# Phrases we must never emit. Matches common ways of *requesting* the secret
# (e.g. "share your OTP", "send me your PIN", "provide your password").
_FORBIDDEN_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(share|send|provide|give|tell|forward|submit|enter|type)\b[^.\n]{0,40}\b(pin|otp|one[-\s]?time\s*password|password|passcode|cvv|cvc|full\s*card\s*number|credit\s*card\s*number|16[-\s]?digit\s*card\s*number)\b",
        r"\b(pin|otp|one[-\s]?time\s*password|passcode|cvv|cvc|full\s*card\s*number|credit\s*card\s*number)\b[^.\n]{0,40}\b(required|needed|please|kindly)\b",
    )
)

# Tokens whose mere mention is suspicious and forces a human review even if no
# explicit "share your X" phrasing is present.
_SENSITIVE_TOKENS: tuple[str, ...] = (
    "pin",
    "otp",
    "one-time password",
    "one time password",
    "password",
    "passcode",
    "cvv",
    "cvc",
    "full card number",
    "credit card number",
    "16-digit card number",
)

_SAFE_REWRITE = (
    "Customer's message is being routed to the appropriate team. "
    "For security, the team will verify the customer's identity through "
    "official channels and will never ask for PIN, OTP, password, or full "
    "card number."
)


def _contains_forbidden_request(text: str) -> bool:
    return any(p.search(text) for p in _FORBIDDEN_REQUEST_PATTERNS)


def _contains_sensitive_token(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _SENSITIVE_TOKENS)


def scrub_summary(summary: str) -> tuple[str, bool]:
    """Return ``(safe_summary, forced_review)``.

    If the summary asks the customer to share a secret, replace it with a
    safe rewrite and force human review. If it merely mentions a sensitive
    token without asking for it, force human review but keep the summary.
    """
    if _contains_forbidden_request(summary):
        return _SAFE_REWRITE, True
    if _contains_sensitive_token(summary):
        return summary, True
    return summary, False
