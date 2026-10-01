from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupIdentifierType,
    CounterpartyLookupProviderError,
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)

DEFAULT_ENDPOINT = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 2_097_152
MAX_MAX_RESPONSE_BYTES = 4_194_304
DEFAULT_MIN_CONNECTION_INTERVAL_SECONDS = 1.0


def _read_bounded(stream, *, max_response_bytes: int) -> bytes:
    body = stream.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ValueError("DaData response exceeds configured max_response_bytes")
    return body


def _request_json(
    endpoint: str,
    api_key: str,
    payload: dict[str, object],
    timeout_seconds: float,
    max_response_bytes: int,
) -> tuple[int, bytes]:
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Token {api_key}",
            "User-Agent": "shema-business-platform/1.5",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.status, _read_bounded(
                response,
                max_response_bytes=max_response_bytes,
            )
    except HTTPError as exc:
        return exc.code, _read_bounded(
            exc,
            max_response_bytes=max_response_bytes,
        )
    except URLError as exc:
        raise ConnectionError("DaData request failed") from exc


@dataclass(frozen=True, slots=True)
class DaDataConfiguration:
    api_key: str
    endpoint: str = DEFAULT_ENDPOINT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    enabled: bool = False
    min_connection_interval_seconds: float = DEFAULT_MIN_CONNECTION_INTERVAL_SECONDS

    @classmethod
    def from_environment(cls) -> DaDataConfiguration:
        return cls(
            api_key=os.getenv("DADATA_API_KEY", "").strip(),
            endpoint=os.getenv("DADATA_ENDPOINT", DEFAULT_ENDPOINT).strip(),
            timeout_seconds=float(
                os.getenv("DADATA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
            ),
            max_response_bytes=int(
                os.getenv("DADATA_MAX_RESPONSE_BYTES", str(DEFAULT_MAX_RESPONSE_BYTES))
            ),
            enabled=os.getenv("DADATA_PROVIDER_EXECUTION_ENABLED", "false").lower() == "true",
            min_connection_interval_seconds=float(
                os.getenv(
                    "DADATA_MIN_CONNECTION_INTERVAL_SECONDS",
                    str(DEFAULT_MIN_CONNECTION_INTERVAL_SECONDS),
                )
            ),
        )

    def __post_init__(self) -> None:
        if self.enabled and not self.api_key.strip():
            raise ValueError("DADATA_API_KEY is required when DaData execution is enabled")
        if not self.endpoint.startswith("https://"):
            raise ValueError("DaData endpoint must use HTTPS")
        if not 0 < self.timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds must be in (0, 30]")
        if not 0 < self.max_response_bytes <= MAX_MAX_RESPONSE_BYTES:
            raise ValueError("max_response_bytes is out of bounds")
        if self.min_connection_interval_seconds <= 0:
            raise ValueError("min_connection_interval_seconds must be positive")


class DaDataCounterpartyLookupProvider:
    provider_id = "dadata_organization_api"

    def __init__(
        self,
        configuration: DaDataConfiguration,
        *,
        requester: Callable[
            [str, str, dict[str, object], float, int], tuple[int, bytes]
        ] | None = None,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._configuration = configuration
        self._requester = requester or _request_json
        self._sleeper = sleeper
        self._rate_lock = Lock()
        self._last_connection_at = 0.0

    def lookup(self, query: CounterpartyLookupQuery) -> CounterpartyProviderRecord:
        if not self._configuration.enabled:
            raise CounterpartyLookupProviderError(
                "PROVIDER_DISABLED",
                "DaData execution is disabled by configuration",
            )
        if not self._configuration.api_key.strip():
            raise CounterpartyLookupProviderError(
                "MISSING_API_KEY",
                "DaData API key is missing",
            )

        payload: dict[str, object] = {"query": query.identifier, "count": 1}
        if query.identifier_type is CounterpartyLookupIdentifierType.OGRNIP:
            payload["type"] = "INDIVIDUAL"

        self._throttle_connection()
        try:
            status, body = self._requester(
                self._configuration.endpoint,
                self._configuration.api_key,
                payload,
                self._configuration.timeout_seconds,
                self._configuration.max_response_bytes,
            )
        except TimeoutError:
            raise CounterpartyLookupProviderError(
                "TRANSPORT_TIMEOUT",
                "DaData request timed out",
                retryable=True,
            ) from None
        except ConnectionError:
            raise CounterpartyLookupProviderError(
                "TRANSPORT_ERROR",
                "DaData transport failed",
                retryable=True,
            ) from None

        if len(body) > self._configuration.max_response_bytes:
            raise CounterpartyLookupProviderError(
                "RESPONSE_TOO_LARGE",
                "DaData response exceeds configured max_response_bytes",
            )

        error_map = {
            400: ("INVALID_REQUEST", False),
            401: ("MISSING_OR_INVALID_API_KEY", False),
            403: ("ACCOUNT_OR_QUOTA_FORBIDDEN", False),
            405: ("METHOD_NOT_ALLOWED", False),
            413: ("REQUEST_TOO_LARGE", False),
            429: ("PROVIDER_RATE_LIMIT", True),
        }
        if status in error_map:
            code, retryable = error_map[status]
            raise CounterpartyLookupProviderError(
                code,
                f"DaData returned HTTP {status}",
                retryable=retryable,
            )
        if status >= 500:
            raise CounterpartyLookupProviderError(
                "PROVIDER_INTERNAL_ERROR",
                f"DaData returned HTTP {status}",
                retryable=True,
            )
        if status != 200:
            raise CounterpartyLookupProviderError(
                "UNEXPECTED_HTTP_STATUS",
                f"DaData returned HTTP {status}",
            )

        try:
            payload_obj = json.loads(body)
        except json.JSONDecodeError as exc:
            raise CounterpartyLookupProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "DaData returned invalid JSON",
            ) from exc

        suggestions = payload_obj.get("suggestions")
        if not isinstance(suggestions, list):
            raise CounterpartyLookupProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "DaData response has no valid suggestions array",
            )
        if not suggestions:
            raise CounterpartyLookupProviderError(
                "NOT_FOUND",
                "DaData returned no matching organization",
            )

        suggestion = suggestions[0]
        if not isinstance(suggestion, dict):
            raise CounterpartyLookupProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "DaData suggestion item is invalid",
            )
        data = suggestion.get("data")
        if not isinstance(data, dict):
            raise CounterpartyLookupProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "DaData suggestion data object is invalid",
            )

        name_obj = data.get("name")
        canonical_name = (
            name_obj.get("full_with_opf")
            if isinstance(name_obj, dict)
            else None
        ) or suggestion.get("unrestricted_value") or suggestion.get("value")
        tax_id = data.get("inn")
        registration_id = data.get("ogrn")
        state = data.get("state")
        legal_status = state.get("status") if isinstance(state, dict) else None
        provider_type = data.get("type")

        if not isinstance(canonical_name, str) or not canonical_name.strip():
            raise CounterpartyLookupProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "DaData response does not contain a company name",
            )

        return CounterpartyProviderRecord(
            provider_id=self.provider_id,
            source_ref="https://dadata.ru/api/find-party/",
            canonical_name=canonical_name.strip(),
            tax_id=str(tax_id).strip() if tax_id else None,
            registration_id=str(registration_id).strip() if registration_id else None,
            legal_status=str(legal_status).strip() if legal_status else None,
            observed_at_ms=(
                state.get("actuality_date")
                if isinstance(state, dict) and isinstance(state.get("actuality_date"), int)
                else None
            ),
            provider_type=provider_type if isinstance(provider_type, str) else None,
        )

    def _throttle_connection(self) -> None:
        with self._rate_lock:
            now = monotonic()
            delay = self._configuration.min_connection_interval_seconds - (
                now - self._last_connection_at
            )
            if delay > 0:
                self._sleeper(delay)
            self._last_connection_at = monotonic()
