import json

import pytest

from shema_platform.adapters.ai.contracts import (
    AIProviderFailureCode,
    AIProviderReadinessState,
    AIProviderRequest,
)
from shema_platform.adapters.ai.yandexgpt import (
    YandexGPTConfiguration,
    YandexGPTExecutionError,
    YandexGPTProvider,
)
from shema_platform.application.ai import AIBudget, AIExecutionContext, AITask


def request(*, max_tokens: int = 100, duration: float = 5) -> AIProviderRequest:
    return AIProviderRequest(
        operation_id="op:1",
        task=AITask("task:1", "qualification", "prompt:v1"),
        input_refs=("identity:1",),
        evidence_refs=("evidence:1",),
        context=AIExecutionContext(
            actor_id="operator",
            resource_ref="identity:1",
            actor_trust_level=2,
            resource_trust_level=2,
            evidence_level=2,
            correlation_id="corr:1",
            configuration_version="cfg:1",
        ),
        budget=AIBudget(
            max_tokens=max_tokens,
            max_cost=1,
            max_duration_seconds=duration,
        ),
        deadline_seconds=duration,
    )


def default_configuration(**overrides: object) -> YandexGPTConfiguration:
    values = {
        "api_key": "secret-not-persisted",
        "model_uri": "gpt://folder/yandexgpt/latest",
        "max_response_bytes": 1_048_576,
        "max_input_chars": 1_000,
        "max_output_tokens": 100,
        "max_cost": 1,
    }
    values.update(overrides)
    return YandexGPTConfiguration(**values)


def response_body(
    *,
    output: str = "approved",
    response_id: str = "resp:1",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> bytes:
    return json.dumps(
        {
            "id": response_id,
            "choices": [
                {
                    "message": {
                        "content": output,
                    }
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
    ).encode("utf-8")


def requester_for(
    *,
    status: int = 200,
    body: bytes | None = None,
    captured: dict[str, object] | None = None,
):
    response = body if body is not None else response_body()

    def requester(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: float,
    ) -> tuple[int, bytes]:
        if captured is not None:
            captured.update(
                {
                    "url": url,
                    "headers": headers,
                    "payload": payload,
                    "timeout": timeout,
                }
            )
        return status, response

    return requester


def build_provider(
    *,
    requester,
    config: YandexGPTConfiguration | None = None,
) -> YandexGPTProvider:
    return YandexGPTProvider(
        config or default_configuration(),
        prompt_renderer=lambda _: "Do the bounded task.",
        cost_estimator=lambda input_tokens, output_tokens: (
            (input_tokens + output_tokens) * 0.01
        ),
        requester=requester,
    )


def test_yandexgpt_success_builds_bounded_request_and_response() -> None:
    captured: dict[str, object] = {}
    instance = build_provider(requester=requester_for(captured=captured))
    result = instance.invoke(request())

    assert result.run.provider_id == "yandexgpt"
    assert result.run.model == "gpt://folder/yandexgpt/latest"
    assert result.run.tokens == 15
    assert result.run.cost == 0.15
    assert result.provider_request_id == "resp:1"
    assert result.provenance_ref == "yandexgpt:response:resp:1"

    assert captured["url"] == "https://ai.api.cloud.yandex.net/v1/chat/completions"
    headers = captured["headers"]
    assert headers["Authorization"] == "Api-Key secret-not-persisted"
    assert headers["Content-Type"] == "application/json"
    payload = captured["payload"]
    assert payload["model"] == "gpt://folder/yandexgpt/latest"
    assert payload["max_tokens"] == 100
    assert payload["messages"] == [
        {"role": "user", "content": "Do the bounded task."}
    ]
    assert captured["timeout"] == 5


def test_api_key_is_not_in_configuration_repr() -> None:
    assert "secret-not-persisted" not in repr(default_configuration())


def test_activation_and_readiness_start_ready() -> None:
    instance = build_provider(requester=requester_for())
    assert instance.activation().enabled is True
    assert instance.activation().explicit is True
    assert instance.readiness().state is AIProviderReadinessState.READY


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, AIProviderFailureCode.AUTHENTICATION),
        (403, AIProviderFailureCode.AUTHORIZATION),
        (429, AIProviderFailureCode.RATE_LIMITED),
        (500, AIProviderFailureCode.TRANSPORT),
        (400, AIProviderFailureCode.INVALID_RESPONSE),
    ],
)
def test_http_failures_are_typed_and_fail_closed(
    status: int,
    code: AIProviderFailureCode,
) -> None:
    instance = build_provider(requester=requester_for(status=status, body=b"{}"))

    with pytest.raises(YandexGPTExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is code
    assert instance.readiness().state is AIProviderReadinessState.UNHEALTHY
    assert instance.readiness().error_code == code.value


def test_invalid_usage_is_rejected_without_guessing_cost() -> None:
    body = response_body()
    data = json.loads(body)
    data["usage"].pop("total_tokens")
    instance = build_provider(
        requester=requester_for(body=json.dumps(data).encode("utf-8"))
    )

    with pytest.raises(YandexGPTExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is AIProviderFailureCode.INVALID_RESPONSE


def test_response_size_limit_fails_closed() -> None:
    instance = build_provider(
        config=default_configuration(max_response_bytes=16),
        requester=requester_for(body=b"{" + b"x" * 100 + b"}"),
    )

    with pytest.raises(YandexGPTExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is AIProviderFailureCode.INVALID_RESPONSE


def test_prompt_input_limit_fails_before_external_call() -> None:
    called = False

    def requester(*args: object, **kwargs: object) -> tuple[int, bytes]:
        nonlocal called
        called = True
        raise AssertionError("external I/O must not happen")

    instance = YandexGPTProvider(
        default_configuration(max_input_chars=4),
        prompt_renderer=lambda _: "too long",
        cost_estimator=lambda *_: 0.1,
        requester=requester,
    )

    with pytest.raises(YandexGPTExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is AIProviderFailureCode.RESOURCE_EXHAUSTED
    assert called is False


def test_deadline_budget_is_bounded_before_external_call() -> None:
    captured: dict[str, object] = {}
    instance = build_provider(
        requester=requester_for(captured=captured),
    )
    result = instance.invoke(request(duration=2))
    assert captured["timeout"] == 2
    assert result.run.duration_seconds <= 2


def test_model_response_must_fit_output_budget() -> None:
    instance = build_provider(
        config=default_configuration(max_output_tokens=2),
        requester=requester_for(body=response_body(completion_tokens=5)),
    )
    with pytest.raises(YandexGPTExecutionError) as exc:
        instance.invoke(request(max_tokens=100))
    assert exc.value.failure.code is AIProviderFailureCode.RESOURCE_EXHAUSTED
