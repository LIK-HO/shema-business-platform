from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SearchRequest(APIModel):
    region: str
    industries: list[str] = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=500)
    selection_level: Literal["candidate", "identified", "verified"] = Field(default="candidate", alias="selectionLevel")


class SearchHitResponse(APIModel):
    candidate_ref: str = Field(alias="candidateRef")
    name: str
    region: str
    industries: list[str]
    source_ref: str = Field(alias="sourceRef") = Field(alias="sourceRef")
    tax_id: str | None = Field(default=None, alias="taxId")
    registration_id: str | None = Field(default=None, alias="registrationId")
    contact_refs: list[str] = Field(default_factory=list, alias="contactRefs")
    selection_level: Literal["candidate", "identified", "verified"]


class SearchResponse(APIModel):
    results: list[SearchHitResponse]
    correlation_id: str = Field(alias="correlationId")


class DiscoveryRequest(APIModel):
    candidate_ref: str
    service_fit: bool = Field(alias="serviceFit")
    economic_fit: bool = Field(alias="economicFit")


class DiscoveryResponse(APIModel):
    candidate_ref: str
    identity_ref: str = Field(alias="entityRef") | None = Field(default=None, alias="identityRef")
    qualification: Literal["qualified", "review", "rejected"]
    reasons: list[str] = []


class ResearchRequest(APIModel):
    subject_ref: str = Field(alias="subjectRef")
    company_type: str
    depth: Literal["R1_IDENTITY", "R2_CONTEXT", "R3_DEEP", "R4_INVESTIGATIVE"]
    query: str


class EvidenceRef(APIModel):
    evidence_id: str = Field(alias="evidenceId")
    claim: str
    source_ref: str
    trust_level: str = Field(alias="trustLevel")
    confidence: float = Field(ge=0, le=1)


class ResearchResponse(APIModel):
    subject_ref: str
    evidence: list[EvidenceRef]


class CommercialActionCreateRequest(APIModel):
    identity_id: str = Field(alias="identityId")
    contact_ref: str
    channel: str
    evidence_refs: list[str] = Field(min_length=1, alias="evidenceRefs")


class CommercialActionResponse(APIModel):
    action_id: str = Field(alias="actionId") = Field(alias="actionId")
    identity_id: str
    contact_ref: str
    channel: str
    status: Literal["draft", "ready", "sent", "failed", "completed", "cancelled"]


class CommercialActionSendRequest(APIModel):
    body: str = Field(min_length=1)


class CommunicationResult(APIModel):
    action_id: str
    channel: str
    external_message_id: str = Field(alias="externalMessageId")
    accepted: bool


class MoneyResponse(APIModel):
    amount: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class OrderLineResponse(APIModel):
    line_id: str = Field(alias="lineId")
    description: str
    quantity: str
    unit_price: MoneyResponse = Field(alias="unitPrice")


class OrderCreateRequest(APIModel):
    action_id: str
    lines: list[OrderLineResponse] = Field(min_length=1)


class OrderResponse(APIModel):
    order_id: str = Field(alias="orderId")
    identity_id: str
    source_action_id: str = Field(alias="sourceActionId")
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
    entry_id: str = Field(alias="entryId")
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
    occurred_at: datetime = Field(alias="occurredAt")


class EconomicResponse(APIModel):
    entity_ref: str
    entries: list[EconomicEntryResponse]


class DiagnosticCheck(APIModel):
    check_id: str = Field(alias="checkId")
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
