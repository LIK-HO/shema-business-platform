from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchRequest(APIModel):
    region: str
    industries: list[str] = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=500)
    selection_level: Literal["candidate", "identified", "verified"] = "candidate"


class SearchHitResponse(APIModel):
    candidate_ref: str
    name: str
    region: str
    industries: list[str]
    source_ref: str
    tax_id: str | None = None
    registration_id: str | None = None
    contact_refs: list[str] = []
    selection_level: Literal["candidate", "identified", "verified"]


class SearchResponse(APIModel):
    results: list[SearchHitResponse]
    correlation_id: str


class DiscoveryRequest(APIModel):
    candidate_ref: str
    service_fit: bool
    economic_fit: bool


class DiscoveryResponse(APIModel):
    candidate_ref: str
    identity_ref: str | None = None
    qualification: Literal["qualified", "review", "rejected"]
    reasons: list[str] = []


class ResearchRequest(APIModel):
    subject_ref: str
    company_type: str
    depth: Literal["R1_IDENTITY", "R2_CONTEXT", "R3_DEEP", "R4_INVESTIGATIVE"]
    query: str


class EvidenceRef(APIModel):
    evidence_id: str
    claim: str
    source_ref: str
    trust_level: str
    confidence: float = Field(ge=0, le=1)


class ResearchResponse(APIModel):
    subject_ref: str
    evidence: list[EvidenceRef]


class CommercialActionCreateRequest(APIModel):
    identity_id: str
    contact_ref: str
    channel: str
    evidence_refs: list[str] = Field(min_length=1)


class CommercialActionResponse(APIModel):
    action_id: str
    identity_id: str
    contact_ref: str
    channel: str
    status: Literal["draft", "ready", "sent", "failed", "completed", "cancelled"]


class CommercialActionSendRequest(APIModel):
    body: str = Field(min_length=1)


class CommunicationResult(APIModel):
    action_id: str
    channel: str
    external_message_id: str
    accepted: bool


class MoneyResponse(APIModel):
    amount: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class OrderLineResponse(APIModel):
    line_id: str
    description: str
    quantity: str
    unit_price: MoneyResponse


class OrderCreateRequest(APIModel):
    action_id: str
    lines: list[OrderLineResponse] = Field(min_length=1)


class OrderResponse(APIModel):
    order_id: str
    identity_id: str
    source_action_id: str
    status: Literal[
        "draft",
        "confirmed",
        "in_progress",
        "completed",
        "cancelled",
        "failed",
    ]
    lines: list[OrderLineResponse]


class EconomicEntryResponse(APIModel):
    entry_id: str
    entity_ref: str
    kind: Literal[
        "provider_cost",
        "ai_cost",
        "order_cost",
        "revenue",
        "adjustment",
    ]
    amount: MoneyResponse
    source_ref: str
    occurred_at: datetime


class EconomicResponse(APIModel):
    entity_ref: str
    entries: list[EconomicEntryResponse]


class DiagnosticCheck(APIModel):
    check_id: str
    status: Literal["pass", "warn", "fail"]
    message: str | None = None


class DiagnosticsResponse(APIModel):
    healthy: bool
    checks: list[DiagnosticCheck]


class ErrorEnvelope(APIModel):
    code: str
    message: str
    correlation_id: str
    details: dict[str, object] | None = None
