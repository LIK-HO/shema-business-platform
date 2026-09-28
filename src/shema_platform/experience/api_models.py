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
    source_ids: list[str] = Field(default_factory=list, alias="sourceIds", max_length=50)
    max_sources: int = Field(default=8, ge=1, le=50, alias="maxSources")
    max_candidates: int = Field(default=500, ge=1, le=5000, alias="maxCandidates")


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


class SearchSourceAttemptResponse(APIModel):
    source_id: str = Field(alias="sourceId")
    source_class: str = Field(alias="sourceClass")
    reliability: str
    access_mode: str = Field(alias="accessMode")
    status: Literal[
        "SEARCHED",
        "SEARCHED_NOT_FOUND",
        "SOURCE_UNAVAILABLE",
        "BUDGET_LIMITED",
    ]
    candidate_count: int = Field(default=0, alias="candidateCount")
    error_code: str | None = Field(default=None, alias="errorCode")


class SearchResponse(APIModel):
    results: list[SearchHitResponse]
    correlation_id: str = Field(alias="correlationId")
    completeness: Literal[
        "NOT_SEARCHED",
        "SEARCHED_NOT_FOUND",
        "SOURCE_UNAVAILABLE",
        "BUDGET_LIMITED",
        "COMPLETE",
    ] = "NOT_SEARCHED"
    plan_version: str = Field(default="search-plan:v1", alias="planVersion")
    source_attempts: list[SearchSourceAttemptResponse] = Field(
        default_factory=list,
        alias="sourceAttempts",
    )


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


class CounterpartyCheckRequest(APIModel):
    """Untrusted lookup request; server-side provider supplies all evidence fields."""
    identifier_type: Literal["INN", "OGRN", "OGRNIP"] = Field(alias="identifierType")
    identifier: str = Field(min_length=1, max_length=32)




class CounterpartyContradictionResponse(APIModel):
    field: str
    existing_value: str = Field(alias="existingValue")
    observed_value: str = Field(alias="observedValue")


class CounterpartyProviderActivationRequest(APIModel):
    reason: str = Field(min_length=1, max_length=256)
    activation_version: str = Field(
        min_length=1,
        max_length=128,
        alias="activationVersion",
    )


class CounterpartyProviderRollbackRequest(APIModel):
    reason: str = Field(min_length=1, max_length=256)


class CounterpartyProviderLookupRequest(APIModel):
    identifier_type: Literal["INN", "OGRN", "OGRNIP"] = Field(alias="identifierType")
    identifier: str = Field(min_length=1, max_length=32)
    claim_confidence: float = Field(ge=0, le=1, alias="claimConfidence")
    expires_at: datetime = Field(alias="expiresAt")
    observed_at: datetime | None = Field(default=None, alias="observedAt")


class CounterpartyProviderLookupResponse(APIModel):
    provider_id: str = Field(alias="providerId")
    source_ref: str = Field(alias="sourceRef")
    canonical_name: str = Field(alias="canonicalName")
    tax_id: str | None = Field(default=None, alias="taxId")
    registration_id: str | None = Field(default=None, alias="registrationId")
    legal_status: str | None = Field(default=None, alias="legalStatus")
    observed_at_ms: int | None = Field(default=None, alias="observedAtMs")
    evidence_ids: list[str] = Field(alias="evidenceIds")
    subject_ref: str = Field(alias="subjectRef")
    identity_ref: str | None = Field(default=None, alias="identityRef")
    contradictions: list[CounterpartyContradictionResponse]
    quarantined: bool
    correlation_id: str = Field(alias="correlationId")


class CounterpartyProviderActivationResponse(APIModel):
    provider_id: str = Field(alias="providerId")
    enabled: bool
    activated_by: str | None = Field(default=None, alias="activatedBy")
    activation_version: str | None = Field(default=None, alias="activationVersion")
    rollback_by: str | None = Field(default=None, alias="rollbackBy")
    rollback_reason: str | None = Field(default=None, alias="rollbackReason")


class CounterpartyCheckResponse(APIModel):
    subject_ref: str = Field(alias="subjectRef")
    identity_ref: str | None = Field(default=None, alias="identityRef")
    identity_state: str | None = Field(default=None, alias="identityState")
    freshness: Literal["fresh", "expired"]
    evidence_ids: list[str] = Field(alias="evidenceIds")
    contradictions: list[CounterpartyContradictionResponse]
    quarantined: bool
    operator_brief: str = Field(alias="operatorBrief")
    correlation_id: str = Field(alias="correlationId")


class AIRunRequest(APIModel):
    task_type: str = Field(min_length=1, alias="taskType")
    prompt_version: str = Field(min_length=1, alias="promptVersion")
    resource_ref: str = Field(min_length=1, alias="resourceRef")
    input_refs: list[str] = Field(min_length=1, max_length=64, alias="inputRefs")
    evidence_refs: list[str] = Field(min_length=1, max_length=64, alias="evidenceRefs")
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



class PublicIntakeRequest(APIModel):
    service_type: str = Field(min_length=2, max_length=120, alias="serviceType")
    location: str = Field(min_length=2, max_length=240)
    preferred_date_or_period: str = Field(
        min_length=2,
        max_length=120,
        alias="preferredDateOrPeriod",
    )
    work_or_cargo_description: str = Field(
        min_length=5,
        max_length=4000,
        alias="workOrCargoDescription",
    )
    contact_name: str = Field(min_length=2, max_length=200, alias="contactName")
    contact_channel: str = Field(min_length=3, max_length=240, alias="contactChannel")
    approximate_volume_or_weight: str | None = Field(
        default=None,
        max_length=500,
        alias="approximateVolumeOrWeight",
    )
    access_or_lifting_constraints: str | None = Field(
        default=None,
        max_length=1000,
        alias="accessOrLiftingConstraints",
    )
    company_name: str | None = Field(default=None, max_length=300, alias="companyName")
    inn: str | None = Field(default=None, min_length=10, max_length=12)
    ogrn_or_ogrnip: str | None = Field(
        default=None,
        min_length=13,
        max_length=15,
        alias="ogrnOrOgrnip",
    )
    comments: str | None = Field(default=None, max_length=2000)
    utm_source: str | None = Field(default=None, max_length=160, alias="utmSource")
    utm_medium: str | None = Field(default=None, max_length=160, alias="utmMedium")
    utm_campaign: str | None = Field(default=None, max_length=240, alias="utmCampaign")
    referrer: str | None = Field(default=None, max_length=500, alias="referrer")
    entry_surface: str = Field(
        default="public_web",
        min_length=2,
        max_length=80,
        alias="entrySurface",
    )
    honeypot: str = Field(default="", max_length=200)


class PublicIntakeResponse(APIModel):
    request_id: str = Field(alias="requestId")
    correlation_id: str = Field(alias="correlationId")
    status: Literal["ACCEPTED", "QUARANTINED_SPAM"]
    preflight_decision: Literal[
        "NORMAL",
        "ATTENTION",
        "BLOCKING_FACT",
        "UNKNOWN",
        "CONFLICTING",
    ] = Field(alias="preflightDecision")
    identity_match: Literal[
        "MATCH",
        "NAME_MISMATCH",
        "NOT_CHECKED",
    ] = Field(alias="identityMatch")
    projection_status: Literal["PROJECTED", "PENDING_PROJECTION"] = Field(
        alias="projectionStatus"
    )
    deduplicated: bool


class OperatorNotificationResponse(APIModel):
    event_id: str = Field(alias="eventId")
    request_id: str = Field(alias="requestId")
    event_type: str = Field(alias="eventType")
    severity: Literal["LOW", "INFO", "ATTENTION", "HIGH", "CRITICAL"]
    payload: dict[str, object]
    created_at: str = Field(alias="createdAt")


class OperatorNotificationListResponse(APIModel):
    notifications: list[OperatorNotificationResponse]
