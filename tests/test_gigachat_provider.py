import json

import pytest

from shema_platform.adapters.ai.contracts import (
    AIProviderFailureCode,
    AIProviderReadinessState,
    AIProviderRequest,
)
from shema_platform.adapters.ai.gigachat import (
    GigaChatConfiguration,
    GigaChatExecutionError,
    GigaChatProvider,
    PRODUCTION_SCOPES,
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


def default_configuration(**overrides: object) -> GigaChatConfiguration:
    values = {
        "authorization_key": "secret-not-persisted",
        "model": "GigaChat-2-Max",
        "scope": "GIGACHAT_API_B2B",
        "max_response_bytes": 1_048_576,
        "max_input_chars": 1_000,
        "max_output_tokens": 100,
        "max_cost": 1,
    }
    values.update(overrides)
    return GigaChatConfiguration(**values)


def chat_body(
    *,
    output: str = "approved",
    response_id: str = "resp:1",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    model: str = "GigaChat-2-Max:2.0.30.01",
) -> bytes:
    return json.dumps(
        {
            "id": response_id,
            "model": model,
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


def token_body(*, expires_at: int = 1_900_000_000) -> bytes:
    return json.dumps(
        {
            "access_token": "access-token-not-persisted",
            "expires_at": expires_at,
        }
    ).encode("utf-8")


def build_provider(
    *,
    chat_requester,
    token_requester,
    clock=lambda: 1_800_000_000.0,
    config: GigaChatConfiguration | None = None,
) -> GigaChatProvider:
    return GigaChatProvider(
        config or default_configuration(),
        prompt_renderer=lambda _: "Do the bounded task.",
        cost_estimator=lambda input_tokens, output_tokens: (
            (input_tokens + output_tokens) * 0.01
        ),
        requester=chat_requester,
        token_requester=token_requester,
        clock=clock,
    )


def test_gigachat_success_builds_token_and_chat_requests() -> None:
    calls: list[tuple[str, str, dict[str, str], bytes | None, float]] = []

    def token_requester(url, method, headers, body, timeout):
        calls.append((url, method, headers, body, timeout))
        return 200, token_body()

    def chat_requester(url, method, headers, body, timeout):
        calls.append((url, method, headers, body, timeout))
        return 200, chat_body()

    instance = build_provider(
        chat_requester=chat_requester,
        token_requester=token_requester,
    )
    result = instance.invoke(request())

    assert result.run.provider_id == "gigachat"
    assert result.run.model == "GigaChat-2-Max"
    assert result.run.tokens == 15
    assert result.run.cost == 0.15
    assert result.provider_request_id == "resp:1"
    assert "GigaChat-2-Max:2.0.30.01" in result.provenance_ref

    token_call = calls[0]
    assert token_call[0] == (
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    )
    assert token_call[1] == "POST"
    assert token_call[2]["Authorization"] == (
        "Basic secret-not-persisted"
    )
    assert token_call[2]["RqUID"]
    assert token_call[3] == b"scope=GIGACHAT_API_B2B"

    chat_call = calls[1]
    assert chat_call[0] == "https://api.giga.chat/v1/chat/completions"
    assert chat_call[1] == "POST"
    assert chat_call[2]["Authorization"] == "Bearer access-token-not-persisted"
    payload = json.loads(chat_call[3])
    assert payload["model"] == "GigaChat-2-Max"
    assert payload["max_tokens"] == 100
    assert payload["messages"] == [
        {"role": "user", "content": "Do the bounded task."}
    ]


def test_authorization_key_and_access_token_are_not_in_repr() -> None:
    config = default_configuration()
    provider = build_provider(
        chat_requester=lambda *args: (200, chat_body()),
        token_requester=lambda *args: (200, token_body()),
        config=config,
    )
    assert "secret-not-persisted" not in repr(config)
    assert "access-token-not-persisted" not in repr(provider)


def test_access_token_is_cached_until_safety_window() -> None:
    current = [1_800_000_000.0]
    calls = 0

    def token_requester(*args):
        nonlocal calls
        calls += 1
        return 200, token_body(expires_at=1_800_001_200)

    def chat_requester(*args):
        return 200, chat_body()

    instance = build_provider(
        chat_requester=chat_requester,
        token_requester=token_requester,
        clock=lambda: current[0],
    )
    instance.invoke(request())
    current[0] = 1_800_000_050.0
    instance.invoke(request())

    assert calls == 1


def test_access_token_refreshes_inside_safety_window() -> None:
    current = [1_800_000_000.0]
    calls = 0

    def token_requester(*args):
        nonlocal calls
        calls += 1
        return 200, token_body(expires_at=1_800_000_120)

    def chat_requester(*args):
        return 200, chat_body()

    instance = build_provider(
        chat_requester=chat_requester,
        token_requester=token_requester,
        clock=lambda: current[0],
    )
    instance.invoke(request())
    current[0] = 1_800_000_100.0
    instance.invoke(request())

    assert calls == 2


def test_api_key_is_not_sent_to_chat_endpoint() -> None:
    captured = {}

    def token_requester(*args):
        return 200, token_body()

    def chat_requester(url, method, headers, body, timeout):
        captured.update(headers)
        return 200, chat_body()

    instance = build_provider(
        chat_requester=chat_requester,
        token_requester=token_requester,
    )
    instance.invoke(request())

    assert captured["Authorization"] == "Bearer access-token-not-persisted"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, AIProviderFailureCode.AUTHENTICATION),
        (403, AIProviderFailureCode.AUTHORIZATION),
        (404, AIProviderFailureCode.MODEL_UNAVAILABLE),
        (422, AIProviderFailureCode.INVALID_RESPONSE),
        (429, AIProviderFailureCode.RATE_LIMITED),
        (500, AIProviderFailureCode.TRANSPORT),
    ],
)
def test_chat_http_failures_are_typed(
    status: int,
    code: AIProviderFailureCode,
) -> None:
    instance = build_provider(
        chat_requester=lambda *args: (status, b"{}"),
        token_requester=lambda *args: (200, token_body()),
    )

    with pytest.raises(GigaChatExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is code
    assert instance.readiness().state is AIProviderReadinessState.UNHEALTHY
    assert instance.readiness().error_code == code.value


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, AIProviderFailureCode.AUTHENTICATION),
        (429, AIProviderFailureCode.RATE_LIMITED),
        (500, AIProviderFailureCode.TRANSPORT),
    ],
)
def test_token_http_failures_are_typed(
    status: int,
    code: AIProviderFailureCode,
) -> None:
    instance = build_provider(
        chat_requester=lambda *args: (200, chat_body()),
        token_requester=lambda *args: (status, b"{}"),
    )

    with pytest.raises(GigaChatExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is code


def test_invalid_usage_is_rejected_without_guessing_cost() -> None:
    data = json.loads(chat_body())
    data["usage"].pop("total_tokens")
    instance = build_provider(
        chat_requester=lambda *args: (200, json.dumps(data).encode()),
        token_requester=lambda *args: (200, token_body()),
    )

    with pytest.raises(GigaChatExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is AIProviderFailureCode.INVALID_RESPONSE


def test_model_identity_must_match_requested_model() -> None:
    instance = build_provider(
        chat_requester=lambda *args: (
            200,
            chat_body(model="AnotherModel:1.0"),
        ),
        token_requester=lambda *args: (200, token_body()),
    )

    with pytest.raises(GigaChatExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is AIProviderFailureCode.INVALID_RESPONSE


def test_response_size_limit_fails_closed() -> None:
    instance = build_provider(
        config=default_configuration(max_response_bytes=16),
        chat_requester=lambda *args: (200, b"{" + b"x" * 100 + b"}"),
        token_requester=lambda *args: (200, token_body()),
    )

    with pytest.raises(GigaChatExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is AIProviderFailureCode.INVALID_RESPONSE


def test_prompt_input_limit_fails_before_external_call() -> None:
    called = False

    def chat_requester(*args):
        nonlocal called
        called = True
        raise AssertionError("external I/O must not happen")

    instance = GigaChatProvider(
        default_configuration(max_input_chars=4),
        prompt_renderer=lambda _: "too long",
        cost_estimator=lambda *_: 0.1,
        requester=chat_requester,
        token_requester=lambda *args: (200, token_body()),
    )

    with pytest.raises(GigaChatExecutionError) as exc:
        instance.invoke(request())

    assert exc.value.failure.code is AIProviderFailureCode.RESOURCE_EXHAUSTED
    assert called is False


def test_production_scopes_exclude_personal_scope() -> None:
    assert PRODUCTION_SCOPES == {
        "GIGACHAT_API_B2B",
        "GIGACHAT_API_CORP",
    }
