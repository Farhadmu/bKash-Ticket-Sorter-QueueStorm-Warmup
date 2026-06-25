"""Direct tests for the safety guard helpers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.safety import scrub_summary  # noqa: E402


def test_clean_summary_passes_through():
    text = "Customer reports a failed payment and wants a status update."
    out, forced = scrub_summary(text)
    assert out == text
    assert forced is False


def test_sharing_request_is_rewritten():
    out, forced = scrub_summary("Please share your OTP with the agent.")
    assert forced is True
    assert "OTP" not in out or "never ask" in out.lower()
    assert "never ask" in out.lower()


def test_card_number_request_is_rewritten():
    out, forced = scrub_summary("Kindly provide your full card number.")
    assert forced is True
    assert "never ask" in out.lower()


def test_sensitive_token_without_request_still_flags():
    out, forced = scrub_summary("Agent noticed the customer mentioned an OTP.")
    assert out == "Agent noticed the customer mentioned an OTP."
    assert forced is True