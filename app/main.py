"""FastAPI application exposing /health and /sort-ticket."""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import classifier, safety
from .config import SETTINGS
from .schemas import (
    CaseType,
    Department,
    Severity,
    SortTicketRequest,
    SortTicketResponse,
)

log = logging.getLogger("app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")

app = FastAPI(title="QueueStorm Sort-Ticket Service", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _enforce_message_size(request: Request) -> None:
    """Reject requests whose declared content length exceeds the cap."""
    length = request.headers.get("content-length")
    if length is None:
        return
    try:
        body_bytes = int(length)
    except ValueError:
        return
    if body_bytes > SETTINGS.max_message_bytes + 512:  # small overhead for envelope
        raise HTTPException(status_code=413, detail="Request body too large")


def _enforce_review(case_type: CaseType, severity: Severity, base_flag: bool) -> bool:
    if severity == Severity.CRITICAL:
        return True
    if case_type == CaseType.PHISHING:
        return True
    return base_flag


@app.post("/sort-ticket", response_model=SortTicketResponse)
async def sort_ticket(request: Request) -> JSONResponse:
    _enforce_message_size(request)

    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        payload = SortTicketRequest.model_validate(raw)
    except Exception as exc:
        # Never echo the raw message back on errors.
        raise HTTPException(status_code=422, detail="Invalid request schema") from exc

    # Enforce message byte length defensively (Content-Length can be missing or lie).
    if len(payload.message.encode("utf-8")) > SETTINGS.max_message_bytes:
        raise HTTPException(status_code=413, detail="Message too long")

    started = time.perf_counter()
    try:
        result: dict[str, Any] = await classifier.classify(payload.message)
    except RuntimeError as exc:
        log.warning("classification failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=502, detail="Classification unavailable") from exc
    elapsed = time.perf_counter() - started
    log.info(
        "ticket=%s case=%s severity=%s ms=%.0f",
        payload.ticket_id,
        result["case_type"].value,
        result["severity"].value,
        elapsed * 1000,
    )

    safe_summary, forced_review = safety.scrub_summary(result["agent_summary"])
    human_review = _enforce_review(result["case_type"], result["severity"], forced_review)

    response = SortTicketResponse(
        ticket_id=payload.ticket_id,
        case_type=result["case_type"],
        severity=result["severity"],
        department=result["department"],
        agent_summary=safe_summary,
        human_review_required=human_review,
        confidence=result["confidence"],
    )
    return JSONResponse(status_code=200, content=response.model_dump())


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
