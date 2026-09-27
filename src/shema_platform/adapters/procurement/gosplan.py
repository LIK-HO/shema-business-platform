from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from shema_platform.application.procurement import (
    ProcurementCollection,
    ProcurementLaw,
    ProcurementOpportunity,
    ProcurementProviderError,
    ProcurementQuery,
    ProcurementSearchResult,
    parse_datetime,
)

DEFAULT_PRODUCT_ENDPOINT = "https://v2.gosplan.info"
DEFAULT_TEST_ENDPOINT = "https://v2test.gosplan.info"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def _read_bounded(stream, *, max_response_bytes: int) -> bytes:
    body = stream.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ValueError("GosPlan response exceeds configured max_response_bytes")
    return body


def _request_json(
    url: str,
    api_key: str,
    timeout_seconds: float,
    max_response_bytes: int,
) -> tuple[int, bytes]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["apikey"] = api_key
    request = Request(url, headers=headers, method="GET")
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
        raise ConnectionError("GosPlan request failed") from exc


@dataclass(frozen=True, slots=True)
class GosplanConfiguration:
    api_key: str = ""
    endpoint: str = DEFAULT_PRODUCT_ENDPOINT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    enabled: bool = False

    @classmethod
    def from_environment(cls) -> GosplanConfiguration:
        return cls(
            api_key=os.getenv("GOSPLAN_API_KEY", "").strip(),
            endpoint=os.getenv("GOSPLAN_ENDPOINT", DEFAULT_PRODUCT_ENDPOINT).strip(),
            timeout_seconds=float(
                os.getenv("GOSPLAN_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
            ),
            max_response_bytes=int(
                os.getenv(
                    "GOSPLAN_MAX_RESPONSE_BYTES",
                    str(DEFAULT_MAX_RESPONSE_BYTES),
                )
            ),
            enabled=os.getenv("GOSPLAN_PROVIDER_EXECUTION_ENABLED", "false").lower() == "true",
        )

    def __post_init__(self) -> None:
        if not self.endpoint.startswith("https://"):
            raise ValueError("GosPlan endpoint must use HTTPS")
        if not 0 < self.timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds must be in (0, 30]")
        if self.max_response_bytes <= 0 or self.max_response_bytes > 16 * 1024 * 1024:
            raise ValueError("max_response_bytes is out of bounds")
        if self.enabled and "v2test.gosplan.info" not in self.endpoint and not self.api_key.strip():
            raise ValueError("GOSPLAN_API_KEY is required for production GosPlan execution")


@dataclass(frozen=True, slots=True)
class GosplanFieldMap:
    external_id: tuple[str, ...] = ("regNumber", "reg_number", "regnumber")
    title: tuple[str, ...] = ("name", "title", "purchaseName", "objectName")
    customer_name: tuple[str, ...] = ("customerName", "customer_name", "customer")
    customer_tax_id: tuple[str, ...] = ("customerInn", "customer_inn", "customerTaxId", "inn")
    max_price: tuple[str, ...] = ("max_price", "maxPrice")
    published_at: tuple[str, ...] = ("publishedAt", "published_at", "publicationDate")
    deadline_at: tuple[str, ...] = ("deadlineAt", "deadline_at", "deadlineDate")
    stage: tuple[str, ...] = ("stage", "status")
    source_url: tuple[str, ...] = ("url", "purchaseUrl", "link")


class GosplanProcurementProvider:
    provider_id = "gosplan_eis_v2"

    _PATHS = {
        (ProcurementLaw.FZ44, ProcurementCollection.PURCHASES): "/fz44/purchases",
        (ProcurementLaw.FZ44, ProcurementCollection.PLANS): "/fz44/tenderplans",
        (ProcurementLaw.FZ223, ProcurementCollection.PURCHASES): "/fz223/purchases",
        (ProcurementLaw.FZ223, ProcurementCollection.PLANS): "/fz223/purchaseplans",
        (ProcurementLaw.PPRF615, ProcurementCollection.PURCHASES): "/pprf615/purchases",
    }

    def __init__(
        self,
        configuration: GosplanConfiguration,
        *,
        requester: Callable[[str, str, float, int], tuple[int, bytes]] | None = None,
        field_map: GosplanFieldMap | None = None,
    ) -> None:
        self._configuration = configuration
        self._requester = requester or _request_json
        self._field_map = field_map or GosplanFieldMap()

    def search(self, query: ProcurementQuery) -> ProcurementSearchResult:
        if not self._configuration.enabled:
            raise ProcurementProviderError(
                "PROVIDER_DISABLED",
                "GosPlan execution is disabled by configuration",
            )
        try:
            path = self._PATHS[(query.law, query.collection)]
        except KeyError as exc:
            raise ProcurementProviderError(
                "UNSUPPORTED_COLLECTION",
                f"no GosPlan endpoint for {query.law.value}/{query.collection.value}",
            ) from exc

        params: dict[str, str | int] = {
            "limit": query.limit,
            "skip": query.skip,
        }
        if query.sort:
            params["sort"] = query.sort
        if query.reg_number:
            params["regNumber"] = query.reg_number
        params.update(dict(query.provider_filters))

        url = f"{self._configuration.endpoint.rstrip('/')}{path}?{urlencode(params)}"
        try:
            status, body = self._requester(
                url,
                self._configuration.api_key,
                self._configuration.timeout_seconds,
                self._configuration.max_response_bytes,
            )
        except TimeoutError:
            raise ProcurementProviderError(
                "TRANSPORT_TIMEOUT",
                "GosPlan request timed out",
                retryable=True,
            ) from None
        except ConnectionError:
            raise ProcurementProviderError(
                "TRANSPORT_ERROR",
                "GosPlan transport failed",
                retryable=True,
            ) from None

        if len(body) > self._configuration.max_response_bytes:
            raise ProcurementProviderError(
                "RESPONSE_TOO_LARGE",
                "GosPlan response exceeds configured max_response_bytes",
            )

        error_map = {
            401: ("MISSING_OR_INVALID_API_KEY", False),
            403: ("API_KEY_FORBIDDEN", False),
            429: ("PROVIDER_RATE_LIMIT", True),
        }
        if status in error_map:
            code, retryable = error_map[status]
            raise ProcurementProviderError(
                code,
                f"GosPlan returned HTTP {status}",
                retryable=retryable,
            )
        if status >= 500:
            raise ProcurementProviderError(
                "PROVIDER_INTERNAL_ERROR",
                f"GosPlan returned HTTP {status}",
                retryable=True,
            )
        if status != 200:
            raise ProcurementProviderError(
                "UNEXPECTED_HTTP_STATUS",
                f"GosPlan returned HTTP {status}",
            )

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProcurementProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "GosPlan returned invalid JSON",
            ) from exc

        if not isinstance(payload, list):
            raise ProcurementProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "GosPlan purchase response must be a JSON array",
            )

        items = tuple(self._parse_item(raw, query.law) for raw in payload)
        return ProcurementSearchResult(
            items=items,
            has_more=len(items) == query.limit,
            next_skip=query.skip + len(items),
            observed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )

    def _parse_item(
        self,
        raw: object,
        law: ProcurementLaw,
    ) -> ProcurementOpportunity:
        if not isinstance(raw, dict):
            raise ProcurementProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "GosPlan purchase item must be an object",
            )

        external_id = self._string_value(raw, self._field_map.external_id)
        title = self._string_value(raw, self._field_map.title)
        if not external_id or not title:
            raise ProcurementProviderError(
                "MALFORMED_PROVIDER_PAYLOAD",
                "GosPlan purchase item lacks required identifier/title",
            )

        max_price = self._decimal_value(raw, self._field_map.max_price)
        return ProcurementOpportunity(
            provider_id=self.provider_id,
            source_ref="https://gosplan.info/api/",
            external_id=external_id,
            law=law,
            title=title,
            customer_name=self._string_value(raw, self._field_map.customer_name),
            customer_tax_id=self._string_value(raw, self._field_map.customer_tax_id),
            max_price=max_price,
            published_at=parse_datetime(self._first_value(raw, self._field_map.published_at)),
            deadline_at=parse_datetime(self._first_value(raw, self._field_map.deadline_at)),
            stage=self._string_value(raw, self._field_map.stage),
            source_url=self._string_value(raw, self._field_map.source_url),
        )

    @staticmethod
    def _first_value(raw: dict[str, object], keys: tuple[str, ...]) -> object | None:
        for key in keys:
            if key in raw and raw[key] not in (None, ""):
                return raw[key]
        return None

    @classmethod
    def _string_value(cls, raw: dict[str, object], keys: tuple[str, ...]) -> str | None:
        value = cls._first_value(raw, keys)
        if isinstance(value, dict):
            for nested_key in ("name", "value", "fullName"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
            return None
        if isinstance(value, (str, int, float)):
            text = str(value).strip()
            return text or None
        return None

    @classmethod
    def _decimal_value(cls, raw: dict[str, object], keys: tuple[str, ...]) -> Decimal | None:
        value = cls._first_value(raw, keys)
        if isinstance(value, (int, float, str)):
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError):
                return None
        return None
