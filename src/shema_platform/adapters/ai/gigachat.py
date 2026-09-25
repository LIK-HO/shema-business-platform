from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from shema_platform.adapters.ai.contracts import (
    AIModelProvenance,
    AIProviderActivation,
    AIProviderAdapter,
    AIProviderDescriptor,
    AIProviderFailure,
    AIProviderFailureCode,
    AIProviderKind,
    AIProviderReadiness,
    AIProviderReadinessState,
    AIProviderRequest,
    AIProviderResourceLimits,
    AIProviderResponse,
    validate_provider_activation,
    validate_provider_response,
)
from shema_platform.application.ai import AIRun

DEFAULT_BASE_URL = "https://api.giga.chat/v1"
DEFAULT_TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 1_048_576
DEFAULT_MAX_INPUT_CHARS = 32_768
DEFAULT_MAX_OUTPUT_TOKENS = 1_024
MAX_TIMEOUT_SECONDS = 30.0
MAX_RESPONSE_BYTES = 4_194_304
MAX_INPUT_CHARS = 131_072
MAX_OUTPUT_TOKENS = 16_384
TOKEN_SAFETY_WINDOW_SECONDS = 30
ALLOWED_SCOPES = frozenset(
    {"GIGACHAT_API_PERS", "GIGACHAT_API_B2B", "GIGACHAT_API_CORP"}
)
PRODUCTION_SCOPES = frozenset({"GIGACHAT_API_B2B", "GIGACHAT_API_CORP"})


class GigaChatExecutionError(RuntimeError):
    def __init__(self, failure: AIProviderFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


@dataclass(frozen=True, slots=True)
class GigaChatConfiguration:
    authorization_key: str = field(repr=False)
    model: str
    scope: str
    base_url: str = DEFAULT_BASE_URL
    token_url: str = DEFAULT_TOKEN_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    max_cost: float = 0.0
    configuration_version: str = "gigachat-config:v1"
    activation_version: str = "gigachat-activation:v1"

    @classmethod
    def from_environment(cls) -> GigaChatConfiguration:
        return cls(
            authorization_key=os.getenv("GIGACHAT_AUTHORIZATION_KEY", "").strip(),
            model=os.getenv("GIGACHAT_MODEL", "").strip(),
            scope=os.getenv("GIGACHAT_SCOPE", "").strip(),
            base_url=os.getenv("GIGACHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            token_url=os.getenv("GIGACHAT_TOKEN_URL", DEFAULT_TOKEN_URL).rstrip("/"),
            timeout_seconds=float(
                os.getenv("GIGACHAT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
            ),
            max_response_bytes=int(
                os.getenv(
                    "GIGACHAT_MAX_RESPONSE_BYTES",
                    str(DEFAULT_MAX_RESPONSE_BYTES),
                )
            ),
            max_input_chars=int(
                os.getenv(
                    "GIGACHAT_MAX_INPUT_CHARS",
                    str(DEFAULT_MAX_INPUT_CHARS),
                )
            ),
            max_output_tokens=int(
                os.getenv(
                    "GIGACHAT_MAX_OUTPUT_TOKENS",
                    str(DEFAULT_MAX_OUTPUT_TOKENS),
                )
            ),
            max_cost=float(os.getenv("GIGACHAT_MAX_COST", "0")),
            configuration_version=os.getenv(
                "GIGACHAT_CONFIGURATION_VERSION",
                "gigachat-config:v1",
            ).strip(),
            activation_version=os.getenv(
                "GIGACHAT_ACTIVATION_VERSION",
                "gigachat-activation:v1",
            ).strip(),
        )

    def __post_init__(self) -> None:
        if not self.authorization_key.strip():
            raise ValueError("GIGACHAT_AUTHORIZATION_KEY is required")
        if not self.model.strip():
            raise ValueError("GIGACHAT_MODEL is required")
        if self.scope not in ALLOWED_SCOPES:
            raise ValueError("GIGACHAT_SCOPE is invalid")
        if not self.base_url.startswith("https://"):
            raise ValueError("GigaChat base_url must use HTTPS")
        if not self.token_url.startswith("https://"):
            raise ValueError("GigaChat token_url must use HTTPS")
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if self.timeout_seconds > MAX_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds must not exceed 30 seconds")
        if (
            self.max_response_bytes <= 0
            or self.max_response_bytes > MAX_RESPONSE_BYTES
        ):
            raise ValueError("max_response_bytes is outside the allowed range")
        if (
            self.max_input_chars <= 0
            or self.max_input_chars > MAX_INPUT_CHARS
        ):
            raise ValueError("max_input_chars is outside the allowed range")
        if (
            self.max_output_tokens <= 0
            or self.max_output_tokens > MAX_OUTPUT_TOKENS
        ):
            raise ValueError("max_output_tokens is outside the allowed range")
        if not isfinite(self.max_cost) or self.max_cost <= 0:
            raise ValueError("max_cost must be finite and positive")
        if not self.configuration_version:
            raise ValueError("configuration_version is required")
        if not self.activation_version:
            raise ValueError("activation_version is required")

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"


@dataclass(slots=True)
class _AccessToken:
    value: str = field(repr=False)
    expires_at: float


def _read_bounded(stream: object, *, max_bytes: int) -> bytes:
    body = stream.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise GigaChatExecutionError(
            AIProviderFailure(
                code=AIProviderFailureCode.INVALID_RESPONSE,
                message=(
                    "GigaChat response exceeded configured response-size limit"
                ),
            )
        )
    return body


def _request(
    url: str,
    *,
    method: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout_seconds: float,
    max_response_bytes: int,
    requester: Callable[..., tuple[int, bytes]] | None,
) -> tuple[int, bytes]:
    if requester is not None:
        return requester(
            url,
            method,
            dict(headers),
            body,
            timeout_seconds,
        )

    request = Request(
        url=url,
        data=body,
        headers=dict(headers),
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.status, _read_bounded(
                response,
                max_bytes=max_response_bytes,
            )
    except HTTPError as exc:
        body = _read_bounded(exc, max_bytes=max_response_bytes)
        return exc.code, body
    except TimeoutError as exc:
        raise GigaChatExecutionError(
            AIProviderFailure(
                code=AIProviderFailureCode.DEADLINE_EXCEEDED,
                message="GigaChat request timed out",
            )
        ) from exc
    except URLError as exc:
        raise GigaChatExecutionError(
            AIProviderFailure(
                code=AIProviderFailureCode.TRANSPORT,
                message="GigaChat request failed at transport level",
            )
        ) from exc


class GigaChatProvider(AIProviderAdapter):
    provider_id = "gigachat"

    def __init__(
        self,
        configuration: GigaChatConfiguration,
        *,
        prompt_renderer: Callable[[AIProviderRequest], str],
        cost_estimator: Callable[[int, int], float],
        requester: Callable[..., tuple[int, bytes]] | None = None,
        token_requester: Callable[..., tuple[int, bytes]] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._configuration = configuration
        self._prompt_renderer = prompt_renderer
        self._cost_estimator = cost_estimator
        self._requester = requester
        self._token_requester = token_requester
        self._clock = clock
        self._token_lock = threading.Lock()
        self._token: _AccessToken | None = None
        self._last_failure_code: str | None = None

        self._descriptor = AIProviderDescriptor(
            provider_id=self.provider_id,
            kind=AIProviderKind.CLOUD,
            model_id=configuration.model,
            model_version="latest",
            configuration_version=configuration.configuration_version,
            capabilities=frozenset({"text_generation", "chat_completion"}),
            resource_limits=AIProviderResourceLimits(
                max_duration_seconds=configuration.timeout_seconds,
                max_response_bytes=configuration.max_response_bytes,
                max_input_chars=configuration.max_input_chars,
                max_output_tokens=configuration.max_output_tokens,
                max_calls=1,
                max_cost=configuration.max_cost,
            ),
            provenance=AIModelProvenance(
                source_ref=(
                    "https://developers.sber.ru/docs/ru/gigachat/"
                    "api/reference/rest/gigachat-api"
                ),
                license_name="GigaChat API use terms",
                license_url=(
                    "https://developers.sber.ru/docs/ru/policies/"
                    "gigachat-agreement/general"
                ),
                license_checked_at=None,
                artifact_digest=None,
                runtime="GigaChat REST API",
                security_status="external-provider-contract-verified",
                free_commercial_use_verified=False,
            ),
        )
        self._activation = AIProviderActivation(
            enabled=True,
            activation_version=configuration.activation_version,
            explicit=True,
            reason="explicit GigaChat adapter activation",
        )
        validate_provider_activation(self._descriptor, self._activation)

    def descriptor(self) -> AIProviderDescriptor:
        return self._descriptor

    def activation(self) -> AIProviderActivation:
        return self._activation

    def readiness(self) -> AIProviderReadiness:
        if self._last_failure_code is not None:
            return AIProviderReadiness(
                provider_id=self.provider_id,
                state=AIProviderReadinessState.UNHEALTHY,
                checked_at=datetime.now(UTC),
                error_code=self._last_failure_code,
            )
        return AIProviderReadiness(
            provider_id=self.provider_id,
            state=AIProviderReadinessState.READY,
            checked_at=datetime.now(UTC),
        )

    def _get_access_token(self, *, timeout_seconds: float) -> str:
        now = self._clock()
        with self._token_lock:
            if self._token is not None and now < self._token.expires_at:
                return self._token.value

            body = urlencode({"scope": self._configuration.scope}).encode("ascii")
            status, response_body = _request(
                self._configuration.token_url,
                method="POST",
                headers={
                    "Authorization": (
                        f"Basic {self._configuration.authorization_key}"
                    ),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "RqUID": str(uuid4()),
                },
                body=body,
                timeout_seconds=timeout_seconds,
                max_response_bytes=self._configuration.max_response_bytes,
                requester=self._token_requester or self._requester,
            )
            if status == 401:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.AUTHENTICATION,
                        message="GigaChat authorization key was rejected",
                    )
                )
            if status == 429:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.RATE_LIMITED,
                        message="GigaChat token rate limit reached",
                    )
                )
            if status >= 500:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.TRANSPORT,
                        message=(
                            f"GigaChat token service returned HTTP {status}"
                        ),
                    )
                )
            if status != 200:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message=(
                            f"GigaChat token request returned HTTP {status}"
                        ),
                    )
                )

            try:
                data = json.loads(response_body)
            except json.JSONDecodeError as exc:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat token endpoint returned invalid JSON",
                    )
                ) from exc

            access_token = (
                data.get("access_token") if isinstance(data, dict) else None
            )
            expires_at = (
                data.get("expires_at") if isinstance(data, dict) else None
            )
            if not isinstance(access_token, str) or not access_token.strip():
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat token response omitted access_token",
                    )
                )
            if not isinstance(expires_at, int) or expires_at <= int(now):
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat token response has invalid expires_at",
                    )
                )

            cached_expiry = float(expires_at - TOKEN_SAFETY_WINDOW_SECONDS)
            if cached_expiry <= now:
                cached_expiry = float(expires_at)
            self._token = _AccessToken(
                value=access_token,
                expires_at=cached_expiry,
            )
            return access_token

    def invoke(self, request: AIProviderRequest) -> AIProviderResponse:
        started = time.monotonic()
        prompt = self._prompt_renderer(request)
        if not isinstance(prompt, str) or not prompt.strip():
            raise GigaChatExecutionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.CONFIGURATION,
                    message=(
                        "GigaChat prompt renderer returned an empty prompt"
                    ),
                )
            )
        if len(prompt) > self._configuration.max_input_chars:
            raise GigaChatExecutionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.RESOURCE_EXHAUSTED,
                    message=(
                        "GigaChat prompt exceeds configured input limit"
                    ),
                )
            )

        timeout = min(
            self._configuration.timeout_seconds,
            request.deadline_seconds,
            request.budget.max_duration_seconds,
        )
        if timeout <= 0:
            raise GigaChatExecutionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.DEADLINE_EXCEEDED,
                    message="GigaChat deadline is already exhausted",
                )
            )

        deadline_at = started + timeout
        payload = {
            "model": self._configuration.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": min(
                request.budget.max_tokens,
                self._configuration.max_output_tokens,
            ),
        }

        try:
            remaining = deadline_at - time.monotonic()
            if remaining <= 0:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.DEADLINE_EXCEEDED,
                        message="GigaChat deadline expired before authorization",
                    )
                )
            access_token = self._get_access_token(timeout_seconds=remaining)

            remaining = deadline_at - time.monotonic()
            if remaining <= 0:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.DEADLINE_EXCEEDED,
                        message="GigaChat deadline expired before generation",
                    )
                )

            status, body = _request(
                self._configuration.endpoint,
                method="POST",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body=json.dumps(
                    payload,
                    separators=(",", ":"),
                ).encode("utf-8"),
                timeout_seconds=remaining,
                max_response_bytes=self._configuration.max_response_bytes,
                requester=self._requester,
            )
            if status == 401:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.AUTHENTICATION,
                        message="GigaChat access token was rejected",
                    )
                )
            if status == 403:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.AUTHORIZATION,
                        message="GigaChat request was not authorized",
                    )
                )
            if status == 404:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.MODEL_UNAVAILABLE,
                        message="GigaChat model was not found",
                    )
                )
            if status == 422:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat rejected request parameters",
                    )
                )
            if status == 429:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.RATE_LIMITED,
                        message="GigaChat request rate limit reached",
                    )
                )
            if status >= 500:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.TRANSPORT,
                        message=f"GigaChat service returned HTTP {status}",
                    )
                )
            if status != 200:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message=(
                            "GigaChat request returned unexpected "
                            f"HTTP {status}"
                        ),
                    )
                )

            try:
                payload_json = json.loads(body)
            except json.JSONDecodeError as exc:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat returned invalid JSON",
                    )
                ) from exc

            choices = (
                payload_json.get("choices")
                if isinstance(payload_json, dict)
                else None
            )
            choice = (
                choices[0]
                if isinstance(choices, list) and choices
                else None
            )
            message = choice.get("message") if isinstance(choice, dict) else None
            output = (
                message.get("content")
                if isinstance(message, dict)
                else None
            )
            usage = (
                payload_json.get("usage")
                if isinstance(payload_json, dict)
                else None
            )
            response_id = (
                payload_json.get("id")
                if isinstance(payload_json, dict)
                else None
            )
            response_model = (
                payload_json.get("model")
                if isinstance(payload_json, dict)
                else None
            )

            if not isinstance(output, str) or not output.strip():
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat response has no usable text content",
                    )
                )
            if not isinstance(usage, dict):
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat response omitted token usage",
                    )
                )
            if (
                not isinstance(response_model, str)
                or not response_model.strip()
                or not (
                    response_model == self._configuration.model
                    or response_model.startswith(
                        f"{self._configuration.model}:"
                    )
                )
            ):
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat response has mismatched model identity",
                    )
                )

            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            if not all(
                isinstance(value, int) and value >= 0
                for value in (
                    input_tokens,
                    output_tokens,
                    total_tokens,
                )
            ):
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="GigaChat response has invalid token usage",
                    )
                )
            if total_tokens != input_tokens + output_tokens:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message=(
                            "GigaChat token usage is internally inconsistent"
                        ),
                    )
                )
            if output_tokens > min(
                request.budget.max_tokens,
                self._configuration.max_output_tokens,
            ):
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.RESOURCE_EXHAUSTED,
                        message=(
                            "GigaChat completion exceeded configured "
                            "token budget"
                        ),
                    )
                )

            try:
                cost = self._cost_estimator(input_tokens, output_tokens)
            except Exception as exc:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.CONFIGURATION,
                        message="GigaChat cost estimator failed",
                    )
                ) from exc
            if not isfinite(cost) or cost < 0:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.CONFIGURATION,
                        message=(
                            "GigaChat cost estimator returned an invalid amount"
                        ),
                    )
                )

            duration = time.monotonic() - started
            if duration > timeout:
                raise GigaChatExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.DEADLINE_EXCEEDED,
                        message=(
                            "GigaChat execution exceeded the bounded deadline"
                        ),
                    )
                )

            run = AIRun(
                run_id=str(uuid4()),
                task_id=request.task.task_id,
                provider_id=self.provider_id,
                model=self._configuration.model,
                model_version="latest",
                prompt_version=request.task.prompt_version,
                input_refs=request.input_refs,
                evidence_refs=request.evidence_refs,
                output=output,
                tokens=total_tokens,
                cost=cost,
                duration_seconds=duration,
            )
            response = AIProviderResponse(
                run=run,
                configuration_version=self._configuration.configuration_version,
                provenance_ref=(
                    f"gigachat:response:"
                    f"{response_id or request.operation_id}:{response_model}"
                ),
                provider_request_id=(
                    response_id
                    if isinstance(response_id, str) and response_id
                    else None
                ),
                observed_at=datetime.now(UTC),
            )
            validate_provider_response(
                self._descriptor,
                request,
                response,
            )
            self._last_failure_code = None
            return response
        except GigaChatExecutionError as exc:
            self._last_failure_code = exc.failure.code.value
            raise
