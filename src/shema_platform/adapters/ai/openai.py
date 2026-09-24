from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from shema_platform.application.ai import AIProvider, AIRun, AITask
from shema_platform.foundation.provider_probe import ProbeResult

DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_INPUT_CHARS = 32_768
MAX_MAX_INPUT_CHARS = 65_536
DEFAULT_MAX_OUTPUT_TOKENS = 4_096
MAX_MAX_OUTPUT_TOKENS = 8_192
DEFAULT_MAX_RESPONSE_BYTES = 1_048_576
MAX_MAX_RESPONSE_BYTES = 4_194_304
DEFAULT_MAX_REQUEST_BODY_BYTES = 262_144
MAX_MAX_REQUEST_BODY_BYTES = 524_288
DEFAULT_MAX_OUTPUT_CHARS = 65_536
MAX_MAX_OUTPUT_CHARS = 262_144
DEFAULT_MAX_REQUESTS_PER_SECOND = 2.0
DEFAULT_MAX_COST_USD_PER_CALL = 0.05
DEFAULT_INPUT_COST_PER_MILLION = 0.10
DEFAULT_OUTPUT_COST_PER_MILLION = 0.50
OPENAI_BASE_URL = "https://api.openai.com"
RESPONSES_PATH = "/v1/responses"

PromptResolver = Callable[[AITask, tuple[str, ...]], str]
EvidenceResolver = Callable[[tuple[str, ...]], tuple[str, ...]]
Requester = Callable[
    [str, str, Mapping[str, str], bytes | None, float],
    tuple[int, bytes],
]


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConnectionError("OpenAI provider rejected an unexpected HTTP redirect")


def _read_bounded(stream, *, max_response_bytes: int) -> bytes:
    body = stream.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ValueError("OpenAI response exceeds configured max_response_bytes")
    return body


def _request_json(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout_seconds: float,
    *,
    max_response_bytes: int,
) -> tuple[int, bytes]:
    request = Request(
        url=url,
        headers=dict(headers),
        data=body,
        method=method,
    )
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            return response.status, _read_bounded(
                response,
                max_response_bytes=max_response_bytes,
            )
    except HTTPError as exc:
        return exc.code, _read_bounded(
            exc,
            max_response_bytes=max_response_bytes,
        )
    except TimeoutError as exc:
        raise TimeoutError("OpenAI provider request timed out") from exc
    except URLError as exc:
        raise ConnectionError("OpenAI provider request failed") from exc


@dataclass(frozen=True, slots=True)
class OpenAIConfiguration:
    api_key: str
    model: str = DEFAULT_MODEL
    base_url: str = OPENAI_BASE_URL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    max_request_body_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS
    max_requests_per_second: float = DEFAULT_MAX_REQUESTS_PER_SECOND
    max_cost_usd_per_call: float = DEFAULT_MAX_COST_USD_PER_CALL
    input_cost_per_million_tokens: float = DEFAULT_INPUT_COST_PER_MILLION
    output_cost_per_million_tokens: float = DEFAULT_OUTPUT_COST_PER_MILLION

    @classmethod
    def from_environment(cls) -> OpenAIConfiguration:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        return cls(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip(),
            timeout_seconds=float(
                os.getenv("OPENAI_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
            ),
            max_input_chars=int(
                os.getenv("OPENAI_MAX_INPUT_CHARS", str(DEFAULT_MAX_INPUT_CHARS))
            ),
            max_output_tokens=int(
                os.getenv(
                    "OPENAI_MAX_OUTPUT_TOKENS",
                    str(DEFAULT_MAX_OUTPUT_TOKENS),
                )
            ),
            max_response_bytes=int(
                os.getenv(
                    "OPENAI_MAX_RESPONSE_BYTES",
                    str(DEFAULT_MAX_RESPONSE_BYTES),
                )
            ),
            max_request_body_bytes=int(
                os.getenv(
                    "OPENAI_MAX_REQUEST_BODY_BYTES",
                    str(DEFAULT_MAX_REQUEST_BODY_BYTES),
                )
            ),
            max_output_chars=int(
                os.getenv(
                    "OPENAI_MAX_OUTPUT_CHARS",
                    str(DEFAULT_MAX_OUTPUT_CHARS),
                )
            ),
            max_requests_per_second=float(
                os.getenv(
                    "OPENAI_MAX_REQUESTS_PER_SECOND",
                    str(DEFAULT_MAX_REQUESTS_PER_SECOND),
                )
            ),
            max_cost_usd_per_call=float(
                os.getenv(
                    "OPENAI_MAX_COST_USD_PER_CALL",
                    str(DEFAULT_MAX_COST_USD_PER_CALL),
                )
            ),
            input_cost_per_million_tokens=float(
                os.getenv(
                    "OPENAI_INPUT_COST_PER_MILLION",
                    str(DEFAULT_INPUT_COST_PER_MILLION),
                )
            ),
            output_cost_per_million_tokens=float(
                os.getenv(
                    "OPENAI_OUTPUT_COST_PER_MILLION",
                    str(DEFAULT_OUTPUT_COST_PER_MILLION),
                )
            ),
        )

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("api_key is required")
        if not self.model.strip():
            raise ValueError("model is required")

        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.openai.com"
            or parsed.port is not None
            or parsed.path.rstrip("/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OpenAI base_url must be exact https://api.openai.com")

        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if self.timeout_seconds > MAX_TIMEOUT_SECONDS:
            raise ValueError("timeout_seconds must not exceed 30")
        if self.max_input_chars <= 0 or self.max_input_chars > MAX_MAX_INPUT_CHARS:
            raise ValueError("max_input_chars is outside the allowed range")
        if (
            self.max_output_tokens <= 0
            or self.max_output_tokens > MAX_MAX_OUTPUT_TOKENS
        ):
            raise ValueError("max_output_tokens is outside the allowed range")
        if (
            self.max_response_bytes <= 0
            or self.max_response_bytes > MAX_MAX_RESPONSE_BYTES
        ):
            raise ValueError("max_response_bytes is outside the allowed range")
        if (
            self.max_request_body_bytes <= 0
            or self.max_request_body_bytes > MAX_MAX_REQUEST_BODY_BYTES
        ):
            raise ValueError("max_request_body_bytes is outside the allowed range")
        if self.max_output_chars <= 0 or self.max_output_chars > MAX_MAX_OUTPUT_CHARS:
            raise ValueError("max_output_chars is outside the allowed range")
        if (
            not isfinite(self.max_requests_per_second)
            or self.max_requests_per_second <= 0
        ):
            raise ValueError("max_requests_per_second must be finite and positive")
        if not isfinite(self.max_cost_usd_per_call) or self.max_cost_usd_per_call <= 0:
            raise ValueError("max_cost_usd_per_call must be finite and positive")
        if (
            not isfinite(self.input_cost_per_million_tokens)
            or self.input_cost_per_million_tokens < 0
            or not isfinite(self.output_cost_per_million_tokens)
            or self.output_cost_per_million_tokens < 0
        ):
            raise ValueError("OpenAI token pricing must be finite and non-negative")

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}{RESPONSES_PATH}"

    @property
    def model_endpoint(self) -> str:
        return f"{self.base_url}/v1/models/{quote(self.model, safe='')}"


class OpenAIProvider(AIProvider):
    """Bounded, stateless OpenAI Responses adapter."""

    provider_id = "openai"

    def __init__(
        self,
        configuration: OpenAIConfiguration,
        *,
        prompt_resolver: PromptResolver,
        evidence_resolver: EvidenceResolver,
        requester: Requester | None = None,
    ) -> None:
        self._configuration = configuration
        self._prompt_resolver = prompt_resolver
        self._evidence_resolver = evidence_resolver
        self._requester = requester or self._default_requester
        self._rate_lock = Lock()
        self._last_request_at = 0.0

    def run(self, task: AITask, *, input_refs: tuple[str, ...]) -> AIRun:
        started = time.monotonic()

        if any(not isinstance(ref, str) or not ref.strip() for ref in input_refs):
            raise ValueError("OpenAI input references must be non-empty strings")

        prompt = self._prompt_resolver(task, input_refs)
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("OpenAI prompt resolver must return non-empty text")
        if len(prompt) > self._configuration.max_input_chars:
            raise ValueError("OpenAI input exceeds configured max_input_chars")

        evidence_refs = tuple(self._evidence_resolver(tuple(input_refs)))
        if any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs):
            raise ValueError("OpenAI evidence resolver returned invalid references")
        evidence_refs = tuple(dict.fromkeys(evidence_refs))

        estimated_input_tokens = len(prompt.encode("utf-8"))
        worst_case_cost = (
            estimated_input_tokens
            * self._configuration.input_cost_per_million_tokens
            / 1_000_000
            + self._configuration.max_output_tokens
            * self._configuration.output_cost_per_million_tokens
            / 1_000_000
        )
        if worst_case_cost > self._configuration.max_cost_usd_per_call:
            raise ValueError("OpenAI request exceeds configured max_cost_usd_per_call")

        payload = {
            "model": self._configuration.model,
            "input": prompt,
            "max_output_tokens": self._configuration.max_output_tokens,
            "store": False,
        }
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > self._configuration.max_request_body_bytes:
            raise ValueError("OpenAI request exceeds configured max_request_body_bytes")

        deadline = time.monotonic() + self._configuration.timeout_seconds
        self._throttle(max_wait_seconds=self._configuration.timeout_seconds)
        timeout_seconds = deadline - time.monotonic()
        if timeout_seconds <= 0:
            raise TimeoutError("OpenAI execution deadline expired before external I/O")

        status, response_body = self._requester(
            "POST",
            self._configuration.endpoint,
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._configuration.api_key}",
                "User-Agent": "shema-business-platform/1.5",
            },
            body,
            timeout_seconds,
        )
        if len(response_body) > self._configuration.max_response_bytes:
            raise ValueError("OpenAI response exceeds configured max_response_bytes")
        if status != 200:
            raise ConnectionError(f"OpenAI Responses request failed with HTTP {status}")

        response = self._decode_object(response_body)
        response_id = response.get("id")
        response_model = response.get("model")
        if (
            not isinstance(response_id, str)
            or not response_id.strip()
            or not isinstance(response_model, str)
            or not response_model.strip()
        ):
            raise ValueError("OpenAI response is missing required identity fields")

        if response.get("status") != "completed":
            raise ValueError("OpenAI response did not complete successfully")

        usage = response.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("OpenAI response is missing usage metrics")

        input_tokens = self._non_negative_int(usage.get("input_tokens"))
        output_tokens = self._non_negative_int(usage.get("output_tokens"))
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
        total_tokens = self._non_negative_int(total_tokens)
        if total_tokens != input_tokens + output_tokens:
            raise ValueError("OpenAI response usage totals are inconsistent")

        cost = (
            input_tokens * self._configuration.input_cost_per_million_tokens
            + output_tokens * self._configuration.output_cost_per_million_tokens
        ) / 1_000_000
        if cost > self._configuration.max_cost_usd_per_call:
            raise ValueError("OpenAI response exceeded configured max_cost_usd_per_call")

        output = self._extract_output_text(response)
        if not output:
            raise ValueError("OpenAI response contains no text output")
        if len(output) > self._configuration.max_output_chars:
            raise ValueError("OpenAI output exceeds configured max_output_chars")

        return AIRun(
            run_id=response_id,
            task_id=task.task_id,
            provider_id=self.provider_id,
            model=self._configuration.model,
            model_version=response_model,
            prompt_version=task.prompt_version,
            input_refs=tuple(input_refs),
            evidence_refs=evidence_refs,
            output=output,
            tokens=total_tokens,
            cost=cost,
            duration_seconds=max(0.0, time.monotonic() - started),
        )

    def check(self) -> ProbeResult:
        """Read-only model visibility/authentication probe; never performs inference."""
        deadline = time.monotonic() + self._configuration.timeout_seconds
        try:
            self._throttle(max_wait_seconds=self._configuration.timeout_seconds)
            timeout_seconds = deadline - time.monotonic()
            if timeout_seconds <= 0:
                return ProbeResult(
                    reachable=False,
                    error_code="DEADLINE_EXPIRED",
                )

            status, body = self._requester(
                "GET",
                self._configuration.model_endpoint,
                {
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._configuration.api_key}",
                    "User-Agent": "shema-business-platform/1.5",
                },
                None,
                timeout_seconds,
            )
            if len(body) > self._configuration.max_response_bytes:
                return ProbeResult(
                    reachable=False,
                    error_code="RESPONSE_TOO_LARGE",
                )
            if status != 200:
                return ProbeResult(
                    reachable=False,
                    error_code=f"HTTP_{status}",
                )

            response = self._decode_object(body)
            if (
                response.get("object") != "model"
                or response.get("id") != self._configuration.model
            ):
                return ProbeResult(
                    reachable=False,
                    error_code="MODEL_MISMATCH",
                )
            return ProbeResult(reachable=True)
        except TimeoutError:
            return ProbeResult(
                reachable=False,
                error_code="TIMEOUT",
            )
        except (ConnectionError, ValueError):
            return ProbeResult(
                reachable=False,
                error_code="PROBE_FAILED",
            )

    def _default_requester(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        return _request_json(
            method,
            url,
            headers,
            body,
            timeout_seconds,
            max_response_bytes=self._configuration.max_response_bytes,
        )

    def _throttle(self, *, max_wait_seconds: float) -> None:
        minimum_interval = 1.0 / self._configuration.max_requests_per_second
        with self._rate_lock:
            now = time.monotonic()
            delay = minimum_interval - (now - self._last_request_at)
            if delay > 0:
                if delay >= max_wait_seconds:
                    raise TimeoutError(
                        "OpenAI execution deadline would expire during rate-limit wait"
                    )
                time.sleep(delay)
            self._last_request_at = time.monotonic()

    @staticmethod
    def _decode_object(body: bytes) -> dict[str, object]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenAI returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("OpenAI response root must be an object")
        return payload

    @staticmethod
    def _non_negative_int(value: object) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise ValueError("OpenAI usage metrics are invalid")
        return value

    @staticmethod
    def _extract_output_text(response: Mapping[str, object]) -> str:
        output = response.get("output")
        if not isinstance(output, list):
            raise ValueError("OpenAI response output is invalid")

        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "output_text":
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
