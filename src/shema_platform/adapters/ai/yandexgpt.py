from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shema_platform.adapters.ai.contracts import (
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

DEFAULT_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 1_048_576
DEFAULT_MAX_INPUT_CHARS = 32_768
DEFAULT_MAX_OUTPUT_TOKENS = 1_024
MAX_TIMEOUT_SECONDS = 30.0
MAX_RESPONSE_BYTES = 4_194_304
MAX_INPUT_CHARS = 131_072
MAX_OUTPUT_TOKENS = 16_384


class YandexGPTExecutionError(RuntimeError):
    def __init__(self, failure: AIProviderFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


@dataclass(frozen=True, slots=True)
class YandexGPTConfiguration:
    api_key: str = field(repr=False)
    model_uri: str = "gpt://placeholder/yandexgpt/latest"
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    max_cost: float = 0.0
    configuration_version: str = "yandexgpt-config:v1"
    activation_version: str = "yandexgpt-activation:v1"

    @classmethod
    def from_environment(cls) -> YandexGPTConfiguration:
        return cls(
            api_key=os.getenv("YANDEXGPT_API_KEY", "").strip(),
            model_uri=os.getenv(
                "YANDEXGPT_MODEL_URI",
                "gpt://placeholder/yandexgpt/latest",
            ).strip(),
            base_url=os.getenv("YANDEXGPT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            timeout_seconds=float(
                os.getenv("YANDEXGPT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
            ),
            max_response_bytes=int(
                os.getenv(
                    "YANDEXGPT_MAX_RESPONSE_BYTES",
                    str(DEFAULT_MAX_RESPONSE_BYTES),
                )
            ),
            max_input_chars=int(
                os.getenv(
                    "YANDEXGPT_MAX_INPUT_CHARS",
                    str(DEFAULT_MAX_INPUT_CHARS),
                )
            ),
            max_output_tokens=int(
                os.getenv(
                    "YANDEXGPT_MAX_OUTPUT_TOKENS",
                    str(DEFAULT_MAX_OUTPUT_TOKENS),
                )
            ),
            max_cost=float(os.getenv("YANDEXGPT_MAX_COST", "0")),
            configuration_version=os.getenv(
                "YANDEXGPT_CONFIGURATION_VERSION",
                "yandexgpt-config:v1",
            ).strip(),
            activation_version=os.getenv(
                "YANDEXGPT_ACTIVATION_VERSION",
                "yandexgpt-activation:v1",
            ).strip(),
        )

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("YANDEXGPT_API_KEY is required")
        if not self.model_uri.startswith("gpt://"):
            raise ValueError("model_uri must use the gpt:// scheme")
        if len(self.model_uri.split("/")) < 4:
            raise ValueError("model_uri must identify a folder and model")
        if not self.base_url.startswith("https://"):
            raise ValueError("YandexGPT base_url must use HTTPS")
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if self.timeout_seconds > MAX_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds must not exceed 30 seconds")
        if self.max_response_bytes <= 0 or self.max_response_bytes > MAX_RESPONSE_BYTES:
            raise ValueError("max_response_bytes is outside the allowed range")
        if self.max_input_chars <= 0 or self.max_input_chars > MAX_INPUT_CHARS:
            raise ValueError("max_input_chars is outside the allowed range")
        if self.max_output_tokens <= 0 or self.max_output_tokens > MAX_OUTPUT_TOKENS:
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


def _read_bounded(stream: object, *, max_bytes: int) -> bytes:
    body = stream.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise YandexGPTExecutionError(
            AIProviderFailure(
                code=AIProviderFailureCode.INVALID_RESPONSE,
                message="YandexGPT response exceeded configured response-size limit",
            )
        )
    return body


def _request_json(
    url: str,
    *,
    api_key: str,
    payload: Mapping[str, object],
    timeout_seconds: float,
    max_response_bytes: int,
    requester: Callable[..., tuple[int, bytes]] | None = None,
) -> tuple[int, bytes]:
    if requester is not None:
        return requester(
            url,
            {
                "Authorization": f"Api-Key {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            payload,
            timeout_seconds,
        )

    request = Request(
        url=url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
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
        raise YandexGPTExecutionError(
            AIProviderFailure(
                code=AIProviderFailureCode.DEADLINE_EXCEEDED,
                message="YandexGPT request timed out",
            )
        ) from exc
    except URLError as exc:
        raise YandexGPTExecutionError(
            AIProviderFailure(
                code=AIProviderFailureCode.TRANSPORT,
                message="YandexGPT request failed at transport level",
            )
        ) from exc


class YandexGPTProvider(AIProviderAdapter):
    provider_id = "yandexgpt"

    def __init__(
        self,
        configuration: YandexGPTConfiguration,
        *,
        prompt_renderer: Callable[[AIProviderRequest], str],
        cost_estimator: Callable[[int, int], float],
        requester: Callable[..., tuple[int, bytes]] | None = None,
    ) -> None:
        self._configuration = configuration
        self._prompt_renderer = prompt_renderer
        self._cost_estimator = cost_estimator
        self._requester = requester
        self._last_failure_code: str | None = None

        self._descriptor = AIProviderDescriptor(
            provider_id=self.provider_id,
            kind=AIProviderKind.CLOUD,
            model_id=configuration.model_uri,
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
            provenance=self._cloud_provenance(),
        )
        self._activation = AIProviderActivation(
            enabled=True,
            activation_version=configuration.activation_version,
            explicit=True,
            reason="explicit YandexGPT adapter activation",
        )
        validate_provider_activation(self._descriptor, self._activation)

    @staticmethod
    def _cloud_provenance():
        from shema_platform.adapters.ai.contracts import AIModelProvenance

        return AIModelProvenance(
            source_ref="https://yandex.cloud/en/docs/overview/api",
            license_name="Yandex Cloud service terms",
            license_url="https://yandex.com/legal/cloud_termsofuse/en/",
            license_checked_at=None,
            artifact_digest=None,
            runtime="Yandex Cloud AI Studio",
            security_status="external-provider-contract-verified",
            free_commercial_use_verified=False,
        )

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

    def invoke(self, request: AIProviderRequest) -> AIProviderResponse:
        started = time.monotonic()
        prompt = self._prompt_renderer(request)
        if not isinstance(prompt, str) or not prompt.strip():
            raise YandexGPTExecutionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.CONFIGURATION,
                    message="YandexGPT prompt renderer returned an empty prompt",
                )
            )
        if len(prompt) > self._configuration.max_input_chars:
            raise YandexGPTExecutionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.RESOURCE_EXHAUSTED,
                    message="YandexGPT prompt exceeds configured input limit",
                )
            )

        timeout = min(
            self._configuration.timeout_seconds,
            request.deadline_seconds,
            request.budget.max_duration_seconds,
        )
        if timeout <= 0:
            raise YandexGPTExecutionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.DEADLINE_EXCEEDED,
                    message="YandexGPT deadline is already exhausted",
                )
            )

        payload = {
            "model": self._configuration.model_uri,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": min(
                request.budget.max_tokens,
                self._configuration.max_output_tokens,
            ),
        }

        try:
            status, body = _request_json(
                self._configuration.endpoint,
                api_key=self._configuration.api_key,
                payload=payload,
                timeout_seconds=timeout,
                max_response_bytes=self._configuration.max_response_bytes,
                requester=self._requester,
            )
            if len(body) > self._configuration.max_response_bytes:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="YandexGPT response exceeded configured response-size limit",
                    )
                )

            if status in (401, 403):
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.AUTHENTICATION
                        if status == 401
                        else AIProviderFailureCode.AUTHORIZATION,
                        message=f"YandexGPT authentication/authorization failed ({status})",
                    )
                )
            if status == 429:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.RATE_LIMITED,
                        message="YandexGPT rate limit reached",
                    )
                )
            if status >= 500:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.TRANSPORT,
                        message=f"YandexGPT service returned HTTP {status}",
                    )
                )
            if status != 200:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message=f"YandexGPT request returned unexpected HTTP {status}",
                    )
                )

            try:
                payload_json = json.loads(body)
            except json.JSONDecodeError as exc:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="YandexGPT returned invalid JSON",
                    )
                ) from exc

            choice = (
                payload_json.get("choices", [None])[0]
                if isinstance(payload_json, dict)
                else None
            )
            message = choice.get("message") if isinstance(choice, dict) else None
            output = message.get("content") if isinstance(message, dict) else None
            usage = payload_json.get("usage") if isinstance(payload_json, dict) else None
            response_id = payload_json.get("id") if isinstance(payload_json, dict) else None

            if not isinstance(output, str) or not output.strip():
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="YandexGPT response has no usable text content",
                    )
                )
            if not isinstance(usage, dict):
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="YandexGPT response omitted token usage",
                    )
                )

            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            if not all(isinstance(value, int) and value >= 0 for value in (
                input_tokens,
                output_tokens,
                total_tokens,
            )):
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="YandexGPT response has invalid token usage",
                    )
                )
            if total_tokens != input_tokens + output_tokens:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.INVALID_RESPONSE,
                        message="YandexGPT token usage is internally inconsistent",
                    )
                )
            if output_tokens > min(
                request.budget.max_tokens,
                self._configuration.max_output_tokens,
            ):
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.RESOURCE_EXHAUSTED,
                        message="YandexGPT completion exceeded configured token budget",
                    )
                )

            try:
                cost = self._cost_estimator(input_tokens, output_tokens)
            except Exception as exc:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.CONFIGURATION,
                        message="YandexGPT cost estimator failed",
                    )
                ) from exc
            if not isfinite(cost) or cost < 0:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.CONFIGURATION,
                        message="YandexGPT cost estimator returned an invalid amount",
                    )
                )

            duration = time.monotonic() - started
            if duration > timeout:
                raise YandexGPTExecutionError(
                    AIProviderFailure(
                        code=AIProviderFailureCode.DEADLINE_EXCEEDED,
                        message="YandexGPT execution exceeded the bounded deadline",
                    )
                )

            from shema_platform.application.ai import AIRun

            run = AIRun(
                run_id=str(response_id or request.operation_id),
                task_id=request.task.task_id,
                provider_id=self.provider_id,
                model=self._configuration.model_uri,
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
                provenance_ref=f"yandexgpt:response:{response_id or request.operation_id}",
                provider_request_id=(
                    response_id if isinstance(response_id, str) and response_id else None
                ),
                observed_at=datetime.now(UTC),
            )
            validate_provider_response(self._descriptor, request, response)
            self._last_failure_code = None
            return response
        except YandexGPTExecutionError as exc:
            self._last_failure_code = exc.failure.code.value
            raise
