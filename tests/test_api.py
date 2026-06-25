"""Tests for the QueueStorm sort-ticket service.

These tests stub out the LLM classifier so they can run without an API key.
They cover the 5 public sample cases from the problem statement, the safety
rule, the schema, and the /health endpoint.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the project root is importable when running `pytest` from anywhere.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Provide a dummy API key before importing the app so Settings loads cleanly.
os.environ.setdefault("LLM_API_KEY", "test-key-not-real")

from app import classifier as classifier_module  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


# --- Fixtures ---------------------------------------------------------------

SAMPLE_CASES = [
    {
        "ticket_id": "T-001",
        "message": "I sent 3000 to wrong number",
        "case_type": "wrong_transfer",
        "severity": "high",
    },
    {
        "ticket_id": "T-002",
        "message": "Payment failed but balance deducted",
        "case_type": "payment_failed",
        "severity": "high",
    },
    {
        "ticket_id": "T-003",
        "message": "Someone called asking my OTP, is that bKash?",
        "case_type": "phishing_or_social_engineering",
        "severity": "critical",
    },
    {
        "ticket_id": "T-004",
        "message": "Please refund my last transaction, I changed my mind",
        "case_type": "refund_request",
        "severity": "low",
    },
    {
        "ticket_id": "T-005",
        "message": "App crashed when I opened it",
        "case_type": "other",
        "severity": "low",
    },
]


def _stub_classifier(case_type: str, severity: str):
    """Return an async stub that mimics classifier.classify using the sample."""
    from app.schemas import CaseType, Department, Severity

    summary = f"Stub summary for {case_type} ticket."
    department_map = {
        "wrong_transfer": Department.DISPUTE_RESOLUTION,
        "payment_failed": Department.PAYMENTS_OPS,
        "phishing_or_social_engineering": Department.FRAUD_RISK,
        "refund_request": Department.CUSTOMER_SUPPORT,
        "other": Department.CUSTOMER_SUPPORT,
    }

    async def _fake(_message: str, *, timeout: float = 25.0):
        return {
            "case_type": CaseType(case_type),
            "severity": Severity(severity),
            "department": department_map[case_type],
            "agent_summary": summary,
            "confidence": 0.9,
        }

    return _fake


# --- /health ---------------------------------------------------------------


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- Schema ----------------------------------------------------------------


def test_ticket_id_is_echoed():
    sample = SAMPLE_CASES[0]
    classifier_module.classify = _stub_classifier(sample["case_type"], sample["severity"])
    resp = client.post(
        "/sort-ticket",
        json={"ticket_id": sample["ticket_id"], "message": sample["message"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket_id"] == sample["ticket_id"]
    assert 0.0 <= body["confidence"] <= 1.0


# --- Public sample cases ---------------------------------------------------


@pytest.mark.parametrize("sample", SAMPLE_CASES, ids=[s["ticket_id"] for s in SAMPLE_CASES])
def test_public_sample_cases(sample):
    classifier_module.classify = _stub_classifier(sample["case_type"], sample["severity"])
    resp = client.post(
        "/sort-ticket",
        json={"ticket_id": sample["ticket_id"], "message": sample["message"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case_type"] == sample["case_type"]
    assert body["severity"] == sample["severity"]


# --- Safety rule -----------------------------------------------------------


SECRET_PHRASES = (
    "share your PIN with us",
    "please send your OTP",
    "kindly provide your password",
    "tell me your full card number",
)


@pytest.mark.parametrize("bad_summary", SECRET_PHRASES)
def test_safety_rule_blocks_forbidden_summary(bad_summary):
    """If the LLM ever returns a summary that asks for a secret, the safety
    guard must rewrite it and force human review."""

    from app.schemas import CaseType, Department, Severity

    async def _bad_classify(_message: str, *, timeout: float = 25.0):
        return {
            "case_type": CaseType.OTHER,
            "severity": Severity.LOW,
            "department": Department.CUSTOMER_SUPPORT,
            "agent_summary": bad_summary,
            "confidence": 0.7,
        }

    classifier_module.classify = _bad_classify
    resp = client.post(
        "/sort-ticket",
        json={"ticket_id": "T-SAFE", "message": "anything"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["human_review_required"] is True
    lowered = body["agent_summary"].lower()
    assert "pin" not in lowered or "never ask" in lowered
    assert "otp" not in lowered or "never ask" in lowered
    assert "password" not in lowered or "never ask" in lowered
    assert "card number" not in lowered or "never ask" in lowered


# --- Phishing routing ------------------------------------------------------


def test_phishing_routes_to_fraud_risk_and_flags_review():
    from app.schemas import CaseType, Department, Severity

    async def _phish_classify(_message: str, *, timeout: float = 25.0):
        # Simulate a bad LLM that misclassifies the department.
        return {
            "case_type": CaseType.PHISHING,
            "severity": Severity.CRITICAL,
            "department": Department.CUSTOMER_SUPPORT,
            "agent_summary": "Customer reports a suspicious call.",
            "confidence": 0.92,
        }

    classifier_module.classify = _phish_classify
    resp = client.post(
        "/sort-ticket",
        json={"ticket_id": "T-PHISH", "message": "Someone called asking my OTP"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case_type"] == "phishing_or_social_engineering"
    assert body["department"] == "fraud_risk"
    assert body["human_review_required"] is True


# --- Input validation ------------------------------------------------------


def test_missing_message_returns_422():
    resp = client.post("/sort-ticket", json={"ticket_id": "T-X"})
    assert resp.status_code == 422


def test_invalid_json_returns_400():
    resp = client.post(
        "/sort-ticket",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400