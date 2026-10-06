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
    selection_level: Literal["candidate", "identified", "verified"] = Field(
        default="candidate",
        alias="selectionLevel",
    )


class SearchHitResponse(APIModel):
    candidate_ref: str = Field(alias="candidateRef")
    name: str
    region: str
    industries: list[str]
    source_ref: str = Field(alias="sourceRef")
    tax_id: str | None = Field(default=None, alias="taxId")
    registration_id: str | None = Field(default=None, alias="registrationId")
    contact_refs: list[str] = Field(default_factory=list, alias="contactRefs")
    selection_level: Literal["candidate", "identified", "verified"] = Field(
        alias="selectionLevel",
    )


class SearchResponse(APIModel):
    results: list[SearchHitResponse]
    correlation_id: str = Field(alias="correlationId")


class DiscoveryRequest(APIModel):
    candidate_ref: str = Field(alias="candidateRef")
    service_fit: bool = Field(alias="serviceFit")
    economic_fit: bool = Field(alias="economicFit")


class DiscoveryResponse(APIModel):
    candidate_ref: str = Field(alias="candidateRef")
    identity_ref: str | None = Field(default=None, alias="identityRef")
    qualification: Literal["qualified", "review", "rejected"]
    reasons: list[str] = Field(default_factory=list)


class ResearchRequest(APIModel):
    subject_ref: str = Field(alias="subjectRef")
    company_type: str = Field(alias="companyType")
    depth: Literal["R1_IDENTITY", "R2_CONTEXT", "R3_DEEP", "R4_INVESTIGATIVE"]
    query: str


class EvidenceRef(APIModel):
    evidence_id: str = Field(alias="evidenceId")
    claim: str
    source_ref: str = Field(alias="sourceRef")
    trust_level: str = Field(alias="trustLevel")
    confidence: float = Field(ge=0, le=1)


class ResearchResponse(APIModel):
    subject_ref: str = Field(alias="subjectRef")
    evidence: list[EvidenceRef]


class AIRunRequest(APIModel):
    task_type: str = Field(min_length=1, alias="taskType")
    prompt_version: str = Field(min_length=1, alias="promptVersion")
    resource_ref: str = Field(min_length=1, alias="resourceRef")
    input_refs: list[str] = Field(min_length=1, alias="inputRefs")
    evidence_refs: list[str] = Field(min_length=1, alias="evidenceRefs")
    evidence_required: bool = Field(default=True, alias="evidenceRequired")
    max_tokens: int = Field(ge=1, le=16384, alias="maxTokens")
    max_cost: float = Field(gt=0, le=1000, alias="maxCost")
    max_duration_seconds: float = Field(gt=0, le=30, alias="maxDurationSeconds")


class AIRunResponse(APIModel):
    run_id: str = Field(alias="runId")
    task_id: str = Field(alias="taskId")
    provider_id: str = Field(alias="providerId")
    model: str
    model_version: str = Field(alias="modelVersion")
    prompt_version: str = Field(alias="promptVersion")
    input_refs: list[str] = Field(alias="inputRefs")
    evidence_refs: list[str] = Field(alias="evidenceRefs")
    output: str
    tokens: int
    cost: float
    duration_seconds: float = Field(alias="durationSeconds")
    correlation_id: str = Field(alias="correlationId")


class CommercialActionCreateRequest(APIModel):
    identity_id: str = Field(alias="identityId")
    contact_ref: str = Field(alias="contactRef")
    channel: str
    evidence_refs: list[str] = Field(min_length=1, alias="evidenceRefs")


class CommercialActionResponse(APIModel):
    action_id: str = Field(alias="actionId")
    identity_id: str = Field(alias="identityId")
    contact_ref: str = Field(alias="contactRef")
    channel: str
    status: Literal[
        "draft",
        "ready",
        "sending",
        "sent",
        "failed",
        "completed",
        "cancelled",
    ]


class CommercialActionSendRequest(APIModel):
    body: str = Field(min_length=1)


class CommunicationResult(APIModel):
    action_id: str = Field(alias="actionId")
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
    action_id: str = Field(alias="actionId")
    lines: list[OrderLineResponse] = Field(min_length=1)


class OrderResponse(APIModel):
    order_id: str = Field(alias="orderId")
    identity_id: str = Field(alias="identityId")
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
    entity_ref: str = Field(alias="entityRef")
    kind: Literal[
        "provider_cost",
        "ai_cost",
        "order_cost",
        "revenue",
        "adjustment",
    ]
    amount: MoneyResponse
    source_ref: str = Field(alias="sourceRef")
    occurred_at: datetime = Field(alias="occurredAt")


class EconomicResponse(APIModel):
    entity_ref: str = Field(alias="entityRef")
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
    correlation_id: str = Field(alias="correlationId")
    details: dict[str, object] | None = None
