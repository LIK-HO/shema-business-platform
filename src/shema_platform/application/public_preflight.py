from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from shema_platform.application.counterparty_lookup import (
    BoundedCounterpartyLookup,
    CounterpartyLookupIdentifierType,
    CounterpartyLookupProvider,
    CounterpartyLookupProviderError,
    CounterpartyLookupQuery,
)
from shema_platform.application.public_intake import (
    CounterpartyPreflightSnapshot,
    IdentityMatch,
    PreflightDecision,
    PublicIntakePayload,
)


@dataclass(frozen=True, slots=True)
class PublicPreflightResult:
    snapshot: CounterpartyPreflightSnapshot
    lookup_performed: bool


def _digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _normalize_name(value: str | None) -> str:
    return re.sub(r"[^0-9а-яa-z]+", "", (value or "").lower())


def _inn_valid(identifier: str) -> bool:
    if len(identifier) == 10:
        weights = (2, 4, 10, 3, 5, 9, 4, 6, 8, 0)
        checksum = (
            sum(
                int(digit) * weight
                for digit, weight in zip(identifier, weights, strict=True)
            )
            % 11
            % 10
        )
        return checksum == int(identifier[-1])
    if len(identifier) == 12:
        weights_1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0, 0)
        weights_2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0)
        check_1 = (
            sum(
                int(digit) * weight
                for digit, weight in zip(identifier, weights_1, strict=True)
            )
            % 11
            % 10
        )
        check_2 = (
            sum(
                int(digit) * weight
                for digit, weight in zip(identifier, weights_2, strict=True)
            )
            % 11
            % 10
        )
        return check_1 == int(identifier[-2]) and check_2 == int(identifier[-1])
    return False


def _ogrn_valid(identifier: str) -> bool:
    if len(identifier) != 13:
        return False
    return (int(identifier[:-1]) % 11) % 10 == int(identifier[-1])


def _ogrnip_valid(identifier: str) -> bool:
    if len(identifier) != 15:
        return False
    return (int(identifier[:-1]) % 13) % 10 == int(identifier[-1])


class PublicCounterpartyPreflightService:
    """Deterministic intake preflight; no GPT and no automatic customer verdict."""

    def __init__(
        self,
        *,
        provider: CounterpartyLookupProvider | None = None,
        cache_lookup: Callable[
            [str, datetime], CounterpartyPreflightSnapshot | None
        ] | None = None,
        consume_lookup_budget: Callable[[str, datetime], None] | None = None,
        cache_store: Callable[[str, CounterpartyPreflightSnapshot], None] | None = None,
        cache_ttl_seconds: int = 300,
        operator_reuse_seconds: int = 900,
        sleeper=None,
    ) -> None:
        if cache_ttl_seconds < 1 or operator_reuse_seconds < cache_ttl_seconds:
            raise ValueError("invalid preflight cache TTLs")
        self._provider = provider
        self._cache_lookup = cache_lookup
        self._consume_lookup_budget = consume_lookup_budget
        self._cache_store = cache_store
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._operator_reuse = timedelta(seconds=operator_reuse_seconds)
        self._sleeper = sleeper

    def run(
        self,
        *,
        payload: PublicIntakePayload,
        request_id: str,
        correlation_id: str,
        public_client_key: str,
        now: datetime,
    ) -> CounterpartyPreflightSnapshot:
        identifier_type, identifier = self._resolve_identifier(payload)
        if identifier is None:
            return self._snapshot(
                request_id=request_id,
                identifier_type=None,
                identifier=None,
                decision=PreflightDecision.UNKNOWN,
                identity_match=IdentityMatch.NOT_CHECKED,
                flags=("IDENTIFIER_NOT_PROVIDED",),
                now=now,
            )

        if not self._checksum_valid(identifier_type, identifier):
            return self._snapshot(
                request_id=request_id,
                identifier_type=identifier_type.value,
                identifier=identifier,
                decision=PreflightDecision.BLOCKING_FACT,
                identity_match=IdentityMatch.NOT_CHECKED,
                flags=("INVALID_IDENTIFIER_CHECKSUM",),
                now=now,
                error_code="INVALID_IDENTIFIER",
            )

        cache_key = f"preflight:v1:{identifier}"
        if self._cache_lookup is not None:
            cached = self._cache_lookup(cache_key, now)
            if cached is not None:
                return cached

        if self._provider is None:
            return self._snapshot(
                request_id=request_id,
                identifier_type=identifier_type.value,
                identifier=identifier,
                decision=PreflightDecision.UNKNOWN,
                identity_match=IdentityMatch.NOT_CHECKED,
                flags=("PROVIDER_UNAVAILABLE",),
                now=now,
                error_code="UNKNOWN_PROVIDER_UNAVAILABLE",
            )

        if self._consume_lookup_budget is not None:
            self._consume_lookup_budget(public_client_key, now)

        try:
            lookup = BoundedCounterpartyLookup(
                self._provider,
                max_attempts=2,
                sleeper=self._sleeper or (lambda _: None),
            )
            record = lookup.lookup(
                CounterpartyLookupQuery(
                    identifier_type=identifier_type,
                    identifier=identifier,
                )
            )
        except (CounterpartyLookupProviderError, TimeoutError, ConnectionError) as exc:
            snapshot = self._snapshot(
                request_id=request_id,
                identifier_type=identifier_type.value,
                identifier=identifier,
                decision=PreflightDecision.UNKNOWN,
                identity_match=IdentityMatch.NOT_CHECKED,
                flags=("PROVIDER_UNAVAILABLE",),
                now=now,
                error_code=getattr(exc, "code", "UNKNOWN_PROVIDER_UNAVAILABLE"),
            )
            return snapshot

        flags: list[str] = []
        supplied_name = payload.company_name or ""
        identity_match = IdentityMatch.NOT_CHECKED
        if supplied_name:
            if _normalize_name(supplied_name) == _normalize_name(record.canonical_name):
                identity_match = IdentityMatch.MATCH
            else:
                identity_match = IdentityMatch.NAME_MISMATCH
                flags.append("LEGAL_NAME_MISMATCH")

        status = (record.legal_status or "").strip().lower()
        if status in {"liquidated", "terminated", "not_registered"}:
            decision = PreflightDecision.BLOCKING_FACT
            flags.append("ENTITY_STATUS_BLOCKING")
        elif "reorgan" in status:
            decision = PreflightDecision.ATTENTION
            flags.append("REORGANIZATION_SIGNAL")
        elif identity_match is IdentityMatch.NAME_MISMATCH:
            decision = PreflightDecision.CONFLICTING
        else:
            decision = PreflightDecision.NORMAL

        observed_at = now
        if record.observed_at_ms is not None:
            try:
                observed_at = datetime.fromtimestamp(
                    record.observed_at_ms / 1000,
                    tz=UTC,
                )
            except (OverflowError, OSError, ValueError):
                flags.append("INVALID_PROVIDER_TIMESTAMP")
                observed_at = now

        snapshot = self._snapshot(
            request_id=request_id,
            identifier_type=identifier_type.value,
            identifier=identifier,
            decision=decision,
            identity_match=identity_match,
            canonical_name=record.canonical_name,
            legal_status=record.legal_status,
            source_ref=record.source_ref,
            provider_id=record.provider_id,
            observed_at=observed_at,
            expires_at=now + self._operator_reuse,
            flags=tuple(flags),
            now=now,
        )
        if self._cache_store is not None:
            self._cache_store(cache_key, snapshot)
        return snapshot

    @staticmethod
    def _resolve_identifier(
        payload: PublicIntakePayload,
    ) -> tuple[CounterpartyLookupIdentifierType, str] | tuple[None, None]:
        inn = _digits(payload.inn)
        registration = _digits(payload.ogrn_or_ogrnip)
        if inn:
            identifier_type = (
                CounterpartyLookupIdentifierType.INN
            )
            return identifier_type, inn
        if registration:
            identifier_type = (
                CounterpartyLookupIdentifierType.OGRNIP
                if len(registration) == 15
                else CounterpartyLookupIdentifierType.OGRN
            )
            return identifier_type, registration
        return None, None

    @staticmethod
    def _checksum_valid(
        identifier_type: CounterpartyLookupIdentifierType,
        identifier: str,
    ) -> bool:
        if identifier_type is CounterpartyLookupIdentifierType.INN:
            return _inn_valid(identifier)
        if identifier_type is CounterpartyLookupIdentifierType.OGRN:
            return _ogrn_valid(identifier)
        return _ogrnip_valid(identifier)

    @staticmethod
    def _snapshot(
        *,
        request_id: str,
        identifier_type: str | None,
        identifier: str | None,
        decision: PreflightDecision,
        identity_match: IdentityMatch,
        now: datetime,
        flags: tuple[str, ...],
        canonical_name: str | None = None,
        legal_status: str | None = None,
        source_ref: str | None = None,
        provider_id: str | None = None,
        observed_at: datetime | None = None,
        expires_at: datetime | None = None,
        error_code: str | None = None,
    ) -> CounterpartyPreflightSnapshot:
        return CounterpartyPreflightSnapshot(
            snapshot_id=f"preflight:{request_id}",
            identifier_type=identifier_type,
            normalized_identifier=identifier,
            decision=decision,
            identity_match=identity_match,
            canonical_name=canonical_name,
            legal_status=legal_status,
            source_ref=source_ref,
            provider_id=provider_id,
            observed_at=observed_at or now,
            expires_at=expires_at or (now + timedelta(minutes=15)),
            flags=flags,
            error_code=error_code,
        )
