import json

import pytest

from shema_platform.adapters.ai.openai import OpenAIConfiguration, OpenAIProvider
from shema_platform.application.ai import AITask


def configuration(**overrides) -> OpenAIConfiguration:
    values = {"api_key": "runtime-secret"}
    values.update(overrides)
    return OpenAIConfiguration(**values)


def resolvers():
    return (
        lambda task, refs: "Classify the supplied business evidence.",
        lambda refs: tuple(refs),
    )


def task() -> AITask:
    return AITask(
        "task-1",
        "qualification",
        "prompt:v1",
    )


def test_openai_provider_calls_responses_api_with_bounded_stateless_request() -> None:
    calls = []

    def requester(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        return (
            200,
            json.dumps(
                {
                    "id": "resp_1",
                    "status": "completed",
                    "model": "gpt-6-luna",
                    "output": [
                        {"type": "reasoning", "id": "rs_1"},
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "qualified"}
                            ],
                        },
                    ],
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 20,
                        "total_tokens": 30,
                    },
                }
            ).encode(),
        )

    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
        requester=requester,
    )

    run = provider.run(task(), input_refs=("evidence:1",))

    method, url, headers, body, timeout = calls[0]
    payload = json.loads(body)

    assert method == "POST"
    assert url.endswith("/v1/responses")
    assert headers["Authorization"] == "Bearer runtime-secret"
    assert payload["model"] == "gpt-6-luna"
    assert payload["store"] is False
    assert payload["max_output_tokens"] == 4096
    assert run.run_id == "resp_1"
    assert run.provider_id == "openai"
    assert run.output == "qualified"
    assert run.tokens == 30
    assert run.cost == pytest.approx(0.000011)
    assert run.evidence_refs == ("evidence:1",)
    assert 0 < timeout <= 15


def test_openai_provider_rejects_preflight_cost_before_request() -> None:
    calls = 0

    def requester(*args):
        nonlocal calls
        calls += 1
        return 200, b"{}"

    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(
            max_input_chars=100,
            max_output_tokens=100,
            max_cost_usd_per_call=0.000001,
        ),
        prompt_resolver=lambda task, refs: "x" * 100,
        evidence_resolver=evidence_resolver,
        requester=requester,
    )

    with pytest.raises(ValueError, match="max_cost_usd_per_call"):
        provider.run(task(), input_refs=("evidence:1",))

    assert calls == 0


def test_openai_provider_rejects_incomplete_response() -> None:
    def requester(*args):
        return (
            200,
            json.dumps(
                {
                    "id": "resp_1",
                    "status": "incomplete",
                    "model": "gpt-6-luna",
                    "output": [],
                    "usage": {
                        "input_tokens": 1,
                        "output_tokens": 1,
                        "total_tokens": 2,
                    },
                }
            ).encode(),
        )

    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
        requester=requester,
    )

    with pytest.raises(ValueError, match="did not complete"):
        provider.run(task(), input_refs=("evidence:1",))


def test_openai_provider_rejects_inconsistent_usage() -> None:
    def requester(*args):
        return (
            200,
            json.dumps(
                {
                    "id": "resp_1",
                    "status": "completed",
                    "model": "gpt-6-luna",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "qualified"}
                            ],
                        }
                    ],
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 20,
                        "total_tokens": 999,
                    },
                }
            ).encode(),
        )

    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
        requester=requester,
    )

    with pytest.raises(ValueError, match="usage totals"):
        provider.run(task(), input_refs=("evidence:1",))


def test_openai_provider_rejects_non_200_without_body_exposure() -> None:
    def requester(*args):
        return 429, b'{"error":{"message":"private response detail"}}'

    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
        requester=requester,
    )

    with pytest.raises(ConnectionError, match="HTTP 429"):
        provider.run(task(), input_refs=("evidence:1",))


def test_openai_provider_rejects_oversized_response_before_json() -> None:
    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(max_response_bytes=32),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
        requester=lambda *args: (200, b"x" * 33),
    )

    with pytest.raises(ValueError, match="max_response_bytes"):
        provider.run(task(), input_refs=("evidence:1",))


def test_openai_provider_rejects_invalid_base_url_and_bounds() -> None:
    with pytest.raises(ValueError, match="exact https"):
        configuration(base_url="https://evil.example")

    with pytest.raises(ValueError, match="exact https"):
        configuration(base_url="https://api.openai.com:443")

    with pytest.raises(ValueError, match="must not exceed 30"):
        configuration(timeout_seconds=31)

    with pytest.raises(ValueError, match="max_output_tokens"):
        configuration(max_output_tokens=9000)


def test_openai_provider_readiness_is_read_only_model_check() -> None:
    calls = []

    def requester(method, url, headers, body, timeout):
        calls.append((method, url, headers, body))
        return 200, json.dumps(
            {
                "id": "gpt-6-luna",
                "object": "model",
                "owned_by": "openai",
            }
        ).encode()

    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
        requester=requester,
    )

    result = provider.check()

    assert result.reachable is True
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/v1/models/gpt-6-luna")
    assert calls[0][3] is None


def test_openai_provider_readiness_fails_closed_on_model_mismatch() -> None:
    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
        requester=lambda *args: (
            200,
            b'{"id":"different-model","object":"model"}',
        ),
    )

    result = provider.check()

    assert result.reachable is False
    assert result.error_code == "MODEL_MISMATCH"


def test_openai_provider_does_not_retry_after_provider_failure() -> None:
    calls = 0

    def requester(*args):
        nonlocal calls
        calls += 1
        return 503, b"{}"

    prompt_resolver, evidence_resolver = resolvers()
    provider = OpenAIProvider(
        configuration(),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
        requester=requester,
    )

    with pytest.raises(ConnectionError):
        provider.run(task(), input_refs=("evidence:1",))

    assert calls == 1
