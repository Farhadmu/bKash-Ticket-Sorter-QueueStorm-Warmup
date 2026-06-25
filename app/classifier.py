"""LLM-based classifier for /sort-ticket.

Calls an OpenAI-compatible chat-completions endpoint and asks the model to
return a strict JSON object matching the response schema. The 5 public sample
cases from the problem statement are inlined as few-shot examples.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from .config import SETTINGS
from .schemas import CaseType, Department, Severity

log = logging.getLogger("classifier")

# Few-shot examples taken directly from the problem statement.
_FEW_SHOT = [
    {
        "message": "I sent 3000 to wrong number",
        "case_type": "wrong_transfer",
        "severity": "high",
        "department": "dispute_resolution",
        "agent_summary": (
            "Customer reports sending 3000 BDT to the wrong number and "
            "requests help recovering the funds."
        ),
        "confidence": 0.93,
    },
    {
        "message": "Payment failed but balance deducted",
        "case_type": "payment_failed",
        "severity": "high",
        "department": "payments_ops",
        "agent_summary": (
            "Customer reports that a payment failed while the balance appears "
            "to have been deducted from the account."
        ),
        "confidence": 0.9,
    },
    {
        "message": "Someone called asking my OTP, is that bKash?",
        "case_type": "phishing_or_social_engineering",
        "severity": "critical",
        "department": "fraud_risk",
        "agent_summary": (
            "Customer reports receiving a call from someone asking for an "
            "OTP, which is a social-engineering attempt."
        ),
        "confidence": 0.95,
    },
    {
        "message": "Please refund my last transaction, I changed my mind",
        "case_type": "refund_request",
        "severity": "low",
        "department": "customer_support",
        "agent_summary": (
            "Customer requests a refund for their most recent transaction, "
            "citing a change of mind."
        ),
        "confidence": 0.88,
    },
    {
        "message": "App crashed when I opened it",
        "case_type": "other",
        "severity": "low",
        "department": "customer_support",
        "agent_summary": (
            "Customer reports that the app crashes on launch and needs "
            "technical assistance."
        ),
        "confidence": 0.85,
    },
]


_SYSTEM_PROMPT = (
    "You are a CRM triage assistant for a digital finance company. "
    "You classify a single customer support message into a structured JSON "
    "object. "
    "You must NEVER ask the customer to share their PIN, OTP, password, CVV, "
    "or full card number in the agent_summary. "
    "Return ONLY valid JSON with exactly these keys: "
    "case_type, severity, department, agent_summary, confidence. "
    "case_type must be one of: wrong_transfer, payment_failed, "
    "refund_request, phishing_or_social_engineering, other. "
    "severity must be one of: low, medium, high, critical. "
    "department must be one of: customer_support, dispute_resolution, "
    "payments_ops, fraud_risk. "
    "confidence must be a float between 0 and 1."
)


def _build_messages(message: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
    ]
    for ex in _FEW_SHOT:
        user = json.dumps({"message": ex["message"]}, ensure_ascii=False)
        assistant = json.dumps(
            {
                "case_type": ex["case_type"],
                "severity": ex["severity"],
                "department": ex["department"],
                "agent_summary": ex["agent_summary"],
                "confidence": ex["confidence"],
            },
            ensure_ascii=False,
        )
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": assistant})

    messages.append({"role": "user", "content": json.dumps({"message": message}, ensure_ascii=False)})
    return messages


def _coerce_enum(value: Any, enum_cls: type, fallback: Any) -> Any:
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            lowered = value.strip().lower().replace(" ", "_")
            for member in enum_cls:
                if member.value == lowered:
                    return member
    return fallback


def _parse_model_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip ```json ... ``` fences if the model added them.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, count=1).strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return json.loads(text)


def _apply_department_policy(case_type: CaseType, department: Department) -> Department:
    # Defensive consistency: phishing always goes to fraud_risk.
    if case_type == CaseType.PHISHING:
        return Department.FRAUD_RISK
    return department


async def classify(message: str, *, timeout: float = 25.0) -> dict[str, Any]:
    """Call the LLM and return a validated result dict.

    Raises ``RuntimeError`` if the LLM call fails or returns malformed output.
    """
    url = f"{SETTINGS.llm_base_url}/chat/completions"
    payload = {
        "model": SETTINGS.llm_model,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "messages": _build_messages(message),
    }
    headers = {
        "Authorization": f"Bearer {SETTINGS.llm_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            # Log only the status, never the body, to avoid leaking customer text.
            log.warning("LLM provider returned status %s", resp.status_code)
            raise RuntimeError(f"LLM provider error: HTTP {resp.status_code}")

        data = resp.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LLM response missing message content") from exc

    parsed = _parse_model_json(content)

    case_type = _coerce_enum(parsed.get("case_type"), CaseType, CaseType.OTHER)
    severity = _coerce_enum(parsed.get("severity"), Severity, Severity.LOW)
    department = _coerce_enum(parsed.get("department"), Department, Department.CUSTOMER_SUPPORT)
    department = _apply_department_policy(case_type, department)

    agent_summary = str(parsed.get("agent_summary") or "").strip()
    if not agent_summary:
        agent_summary = "Customer message received and queued for review."

    try:
        confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return {
        "case_type": case_type,
        "severity": severity,
        "department": department,
        "agent_summary": agent_summary,
        "confidence": confidence,
    }
