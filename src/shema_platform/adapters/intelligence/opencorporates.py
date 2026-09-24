from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

DEFAULT_MAX_RESPONSE_BYTES = 1_048_576
MAX_MAX_RESPONSE_BYTES = 4_194_304
DEFAULT_MAX_QUERY_CHARS = 1_024
MAX_MAX_QUERY_CHARS = 4_096
DEFAULT_MAX_REQUEST_URL_BYTES = 8_192
MAX_MAX_REQUEST_URL_BYTES = 16_384
MAX_COMPANY_NAME_CHARS = 512
MAX_JURISDICTION_CODE_CHARS = 32
MAX_COMPANY_NUMBER_CHARS = 128
MAX_CURRENT_STATUS_CHARS = 64


def _canonicalize_provenance_url(source_ref: str) -> str | None:
    try:
        parsed = urlsplit(source_ref)
    except ValueError:
        return None

    path = parsed.path.rstrip("/")
    segments = path.split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "opencorporates.com"
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or len(segments) != 4
        or segments[0] != ""
        or segments[1] != "companies"
        or not segments[2]
        or not segments[3]
    ):
        return None

    return (
        "https://opencorporates.com/companies/"
        f"{segments[2]}/{segments[3]}"
    )


def _bounded_observation_text(
    value: object,
    *,
    max_chars: int,
    default: str,
) -> str | None:
    if value is None:
        return default
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_chars:
        return None
    return cleaned


def _build_request_url(
    url: str,
    params: Mapping[str, str],
    *,
    max_request_url_bytes: int,
) -> str:
    request_url = f"{url}?{urlencode(params)}"
    if len(request_url.encode("utf-8")) > max_request_url_bytes:
        raise ValueError(
            "OpenCorporates request URL exceeds configured max_request_url_bytes"
        )
    return request_url


def _read_bounded(stream, *, max_response_bytes: int) -> bytes:
    body = stream.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ValueError(
            "OpenCorporates response exceeds configured max_response_bytes"
        )
    return body


def _request_json(
    url: str,
    params: Mapping[str, str],
    timeout_seconds: float,
    max_response_bytes: int,
    max_request_url_bytes: int,
) -> tuple[int, bytes]:
    request = Request(
        url=_build_request_url(
            url,
            params,
            max_request_url_bytes=max_request_url_bytes,
        ),
        headers={
            "Accept": "application/json",
            "User-Agent": "shema-business-platform/1.5",
        },
        method="GET",
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
        raise ConnectionError("OpenCorporates request failed") from exc


@dataclass(frozen=True, slots=True)
class OpenCorporatesConfiguration:
    api_token: str
    api_version: str = "0.4"
    base_url: str = "https://api.opencorporates.com"
    timeout_seconds: float = 5.0
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    max_query_chars: int = DEFAULT_MAX_QUERY_CHARS
    max_request_url_bytes: int = DEFAULT_MAX_REQUEST_URL_BYTES
    cost_per_call: float = 0.0
    max_requests_per_second: float = 1.0
    coverage: frozenset[str] = frozenset(
        {"company", "logistics", "construction", "trade"}
    )
    confidence: float = 0.8

    @classmethod
    def from_environment(cls) -> OpenCorporatesConfiguration:
        token = os.getenv("OPENCORPORATES_API_TOKEN", "").strip()
        if not token:
            raise ValueError("OPENCORPORATES_API_TOKEN is required")
        return cls(
            api_token=token,
            api_version=os.getenv("OPENCORPORATES_API_VERSION", "0.4").strip(),
            timeout_seconds=float(
                os.getenv("OPENCORPORATES_TIMEOUT_SECONDS", "5")
            ),
            max_response_bytes=int(
                os.getenv(
                    "OPENCORPORATES_MAX_RESPONSE_BYTES",
                    str(DEFAULT_MAX_RESPONSE_BYTES),
                )
            ),
            max_query_chars=int(
                os.getenv(
                    "OPENCORPORATES_MAX_QUERY_CHARS",
                    str(DEFAULT_MAX_QUERY_CHARS),
                )
            ),
            max_request_url_bytes=int(
                os.getenv(
                    "OPENCORPORATES_MAX_REQUEST_URL_BYTES",
                    str(DEFAULT_MAX_REQUEST_URL_BYTES),
                )
            ),
            cost_per_call=float(
                os.getenv("OPENCORPORATES_COST_PER_CALL", "0")
            ),
            max_requests_per_second=float(
                os.getenv("OPENCORPORATES_MAX_REQUESTS_PER_SECOND", "1")
            ),
            confidence=float(
                os.getenv("OPENCORPORATES_CONFIDENCE", "0.8")
            ),
            coverage=frozenset(
                item.strip()
                for item in os.getenv(
                    "OPENCORPORATES_COVERAGE",
                    "company,logistics,construction,trade",
                ).split(",")
                if item.strip()
            ),
        )

    def __post_init__(self) -> None:
        if not self.api_token.strip():
            raise ValueError("api_token is required")
        if not self.api_version.strip():
            raise ValueError("api_version is required")
        if not self.base_url.startswith("https://"):
            raise ValueError("OpenCorporates base_url must use HTTPS")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.timeout_seconds > 30.0:
            raise ValueError("timeout_seconds must not exceed 30")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if self.max_response_bytes > MAX_MAX_RESPONSE_BYTES:
            raise ValueError(
                "max_response_bytes must not exceed 4194304"
            )
        if self.max_query_chars <= 0:
            raise ValueError("max_query_chars must be positive")
        if self.max_query_chars > MAX_MAX_QUERY_CHARS:
            raise ValueError(
                "max_query_chars must not exceed 4096"
            )
        if self.max_request_url_bytes <= 0:
            raise ValueError("max_request_url_bytes must be positive")
        if self.max_request_url_bytes > MAX_MAX_REQUEST_URL_BYTES:
            raise ValueError(
                "max_request_url_bytes must not exceed 16384"
            )
        if self.cost_per_call < 0:
            raise ValueError("cost_per_call cannot be negative")
        if self.max_requests_per_second <= 0:
            raise ValueError("max_requests_per_second must be positive")
        if not self.coverage:
            raise ValueError("coverage cannot be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def endpoint(self) -> str:
        return (
            f"{self.base_url.rstrip('/')}"
            f"/v{self.api_version}/companies/search"
        )


class OpenCorporatesProvider:
    """Provider adapter that turns OpenCorporates observations into evidence-ready results."""

    def __init__(
        self,
        configuration: OpenCorporatesConfiguration,
        *,
        requester: Callable[
            [str, Mapping[str, str], float], tuple[int, bytes]
        ] | None = None,
    ) -> None:
        from shema_platform.application.research import ProviderCapability

        self._configuration = configuration
        if requester is None:
            self._requester = (
                lambda url, params, timeout: _request_json(
                    url,
                    params,
                    timeout,
                    max_response_bytes=configuration.max_response_bytes,
                    max_request_url_bytes=(
                        configuration.max_request_url_bytes
                    ),
                )
            )
        else:
            self._requester = requester
        self._rate_lock = Lock()
        self._last_request_at = 0.0
        self.capability = ProviderCapability(
            provider_id="opencorporates",
            source_class="corporate_registry_aggregator",
            coverage=configuration.coverage,
            cost_per_call=configuration.cost_per_call,
            max_requests_per_second=configuration.max_requests_per_second,
            estimated_tokens_per_call=0,
            estimated_latency_seconds=configuration.timeout_seconds,
        )

    def research(
        self,
        query: str,
        *,
        max_sources: int,
        timeout_seconds: float | None = None,
    ):
        from shema_platform.application.research import ProviderResult

        if not isinstance(query, str):
            raise TypeError("OpenCorporates query must be a string")

        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("OpenCorporates query is required")
        if len(cleaned_query) > self._configuration.max_query_chars:
            raise ValueError(
                "OpenCorporates query exceeds configured max_query_chars"
            )
        if max_sources <= 0:
            raise ValueError("max_sources must be positive")

        requested = min(max_sources, 50)
        params = {
            "api_token": self._configuration.api_token,
            "q": cleaned_query,
            "per_page": str(requested),
            "order": "score",
        }
        _build_request_url(
            self._configuration.endpoint,
            params,
            max_request_url_bytes=self._configuration.max_request_url_bytes,
        )

        request_timeout = self._configuration.timeout_seconds
        if timeout_seconds is not None:
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds override must be positive")
            request_timeout = min(request_timeout, timeout_seconds)

        deadline = time.monotonic() + request_timeout
        self._throttle(max_wait_seconds=request_timeout)
        request_timeout = deadline - time.monotonic()
        if request_timeout <= 0:
            raise TimeoutError(
                "OpenCorporates execution deadline expired before external I/O"
            )

        status, body = self._requester(
            self._configuration.endpoint,
            params,
            request_timeout,
        )
        if len(body) > self._configuration.max_response_bytes:
            raise ValueError(
                "OpenCorporates response exceeds configured max_response_bytes"
            )

        if status != 200:
            raise ConnectionError(
                f"OpenCorporates request failed with HTTP {status}"
            )

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenCorporates returned invalid JSON") from exc

        companies = payload.get("results", {}).get("companies", [])
        if not isinstance(companies, list):
            raise ValueError(
                "OpenCorporates response has invalid companies payload"
            )

        claims: list[str] = []
        source_refs: list[str] = []

        for item in companies[:requested]:
            company = item.get("company") if isinstance(item, dict) else None
            if not isinstance(company, dict):
                continue

            source_ref = company.get("opencorporates_url")
            name = company.get("name")
            canonical_source_ref = (
                _canonicalize_provenance_url(source_ref)
                if isinstance(source_ref, str)
                else None
            )
            if canonical_source_ref is None:
                continue
            clean_name = _bounded_observation_text(
                name,
                max_chars=MAX_COMPANY_NAME_CHARS,
                default="",
            )
            jurisdiction = _bounded_observation_text(
                company.get("jurisdiction_code"),
                max_chars=MAX_JURISDICTION_CODE_CHARS,
                default="unknown",
            )
            company_number = _bounded_observation_text(
                company.get("company_number"),
                max_chars=MAX_COMPANY_NUMBER_CHARS,
                default="unknown",
            )
            current_status = _bounded_observation_text(
                company.get("current_status"),
                max_chars=MAX_CURRENT_STATUS_CHARS,
                default="unknown",
            )
            if (
                not clean_name
                or jurisdiction is None
                or company_number is None
                or current_status is None
            ):
                continue
            claims.append(
                "OpenCorporates company observation: "
                f"name={name.strip()}; "
                f"company_number={company_number}; "
                f"jurisdiction={jurisdiction}; "
                f"current_status={current_status}"
            )
            source_refs.append(canonical_source_ref)

        return ProviderResult(
            provider_id=self.capability.provider_id,
            source_class=self.capability.source_class,
            claims=tuple(claims),
            source_refs=tuple(dict.fromkeys(source_refs)),
            confidence=self._configuration.confidence,
            cost=self._configuration.cost_per_call,
            latency_seconds=self._configuration.timeout_seconds,
            tokens=0,
        )

    @property
    def provider_id(self) -> str:
        return "opencorporates"

    def check(self, *, call_budget=None):
        from shema_platform.foundation.provider_budget import ProviderCallBudget
        from shema_platform.foundation.provider_probe import ProbeResult

        if call_budget is not None:
            if not isinstance(call_budget, ProviderCallBudget):
                raise TypeError("call_budget must be ProviderCallBudget")
            call_budget.reserve()

        params = {
            "api_token": self._configuration.api_token,
            "q": "__shema_provider_readiness_probe__",
            "per_page": "1",
            "order": "score",
        }
        _build_request_url(
            self._configuration.endpoint,
            params,
            max_request_url_bytes=self._configuration.max_request_url_bytes,
        )

        request_timeout = self._configuration.timeout_seconds
        deadline = time.monotonic() + request_timeout
        self._throttle(max_wait_seconds=request_timeout)
        request_timeout = deadline - time.monotonic()
        if request_timeout <= 0:
            raise TimeoutError(
                "OpenCorporates execution deadline expired before external I/O"
            )

        try:
            status, _ = self._requester(
                self._configuration.endpoint,
                params,
                request_timeout,
            )
        except Exception:
            return ProbeResult(
                reachable=False,
                error_code="CONNECTION_ERROR",
            )

        if status == 200:
            return ProbeResult(reachable=True)

        return ProbeResult(
            reachable=False,
            error_code=f"HTTP_{status}",
        )

    def _throttle(self, *, max_wait_seconds: float | None = None) -> None:
        minimum_interval = 1.0 / self.capability.max_requests_per_second
        with self._rate_lock:
            now = time.monotonic()
            delay = minimum_interval - (now - self._last_request_at)
            if delay > 0:
                if max_wait_seconds is not None and delay >= max_wait_seconds:
                    raise TimeoutError(
                        "OpenCorporates execution deadline would expire during rate-limit wait"
                    )
                time.sleep(delay)
            self._last_request_at = time.monotonic()
