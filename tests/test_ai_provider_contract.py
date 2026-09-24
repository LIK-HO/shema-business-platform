from datetime import UTC, datetime

import pytest

from shema_platform.adapters.ai.contracts import (
    AIModelProvenance,
    AIProviderActivation,
    AIProviderDescriptor,
    AIProviderFailure,
    AIProviderFailureCode,
    AIProviderKind,
    AIProviderReadiness,
    AIProviderReadinessState,
    AIProviderRequest,
    AIProviderResourceLimits,
    AIProviderResponse,
    AIProviderRoutingPolicy,
    validate_provider_activation,
    validate_provider_response,
)
from shema_platform.application.ai import (
    AIBudget,
    AIExecutionContext,
    AIRun,
    AITask,
)


def limits() -> AIProviderResourceLimits:
    return AIProviderResourceLimits(
        max_duration_seconds=10,
        max_response_bytes=1_048_576,
        max_input_chars=16_384,
        max_output_tokens=512,
        max_calls=1,
        max_cost=0.50,
    )


def provenance(*, free: bool, digest: str | None = 'sha256:abc') -> AIModelProvenance:
    return AIModelProvenance(
        source_ref='https://example.test/model',
        license_name='Example License',
        license_url='https://example.test/license',
        license_checked_at=(
            datetime(2026, 9, 24, tzinfo=UTC) if free else None
        ),
        artifact_digest=digest if free else None,
        runtime='example-runtime',
        security_status='verified',
        free_commercial_use_verified=free,
    )


def descriptor(
    provider_id: str,
    kind: AIProviderKind,
    *,
    free: bool,
) -> AIProviderDescriptor:
    return AIProviderDescriptor(
        provider_id=provider_id,
        kind=kind,
        model_id='model-1',
        model_version='1',
        configuration_version='cfg:1',
        capabilities=frozenset({'text_generation'}),
        resource_limits=limits(),
        provenance=provenance(free=free),
    )


def activation() -> AIProviderActivation:
    return AIProviderActivation(
        enabled=True,
        activation_version='activation:1',
        explicit=True,
        reason='approved integration test',
    )


def test_cloud_allowlist_is_fail_closed() -> None:
    validate_provider_activation(
        descriptor('yandexgpt', AIProviderKind.CLOUD, free=False),
        activation(),
    )
    validate_provider_activation(
        descriptor('gigachat', AIProviderKind.CLOUD, free=False),
        activation(),
    )

    with pytest.raises(ValueError, match='outside the approved allowlist'):
        validate_provider_activation(
            descriptor('unexpected-cloud', AIProviderKind.CLOUD, free=False),
            activation(),
        )


def test_local_model_requires_free_commercial_license_evidence() -> None:
    with pytest.raises(ValueError, match='verified free commercial use'):
        validate_provider_activation(
            descriptor('local:test', AIProviderKind.LOCAL_SELF_HOSTED, free=False),
            activation(),
        )

    validate_provider_activation(
        descriptor('local:test', AIProviderKind.LOCAL_SELF_HOSTED, free=True),
        activation(),
    )


def test_local_free_use_requires_artifact_digest() -> None:
    with pytest.raises(ValueError, match='artifact_digest'):
        AIModelProvenance(
            source_ref='https://example.test/model',
            license_name='Example License',
            license_url='https://example.test/license',
            license_checked_at=datetime(2026, 9, 24, tzinfo=UTC),
            artifact_digest=None,
            runtime='example-runtime',
            security_status='verified',
            free_commercial_use_verified=True,
        )


def test_implicit_fallback_is_forbidden() -> None:
    assert AIProviderRoutingPolicy() == AIProviderRoutingPolicy()
    with pytest.raises(ValueError, match='cloud-to-local'):
        AIProviderRoutingPolicy(implicit_cloud_to_local_fallback=True)
    with pytest.raises(ValueError, match='local-to-cloud'):
        AIProviderRoutingPolicy(implicit_local_to_cloud_fallback=True)


def test_retry_requires_evidence() -> None:
    with pytest.raises(ValueError, match='retry-safety evidence'):
        AIProviderFailure(
            code=AIProviderFailureCode.TRANSPORT,
            message='temporary network failure',
            retry_allowed=True,
        )

    AIProviderFailure(
        code=AIProviderFailureCode.TRANSPORT,
        message='temporary network failure',
        retry_allowed=True,
        retry_safety_evidence_ref='evidence:provider-retry-v1',
    )


def test_provider_response_is_bounded_and_matches_request() -> None:
    task = AITask('task:1', 'qualification', 'prompt:v1')
    request = AIProviderRequest(
        operation_id='op:1',
        task=task,
        input_refs=('identity:1',),
        evidence_refs=('evidence:1',),
        context=AIExecutionContext(
            actor_id='operator',
            resource_ref='identity:1',
            actor_trust_level=2,
            resource_trust_level=2,
            evidence_level=2,
            correlation_id='corr:1',
            configuration_version='cfg:1',
        ),
        budget=AIBudget(max_tokens=100, max_cost=1, max_duration_seconds=5),
        deadline_seconds=5,
    )
    response = AIProviderResponse(
        run=AIRun(
            run_id='run:1',
            task_id='task:1',
            provider_id='yandexgpt',
            model='model-1',
            model_version='1',
            prompt_version='prompt:v1',
            input_refs=('identity:1',),
            evidence_refs=('evidence:1',),
            output='ok',
            tokens=10,
            cost=0.01,
            duration_seconds=1,
        ),
        configuration_version='cfg:1',
        provenance_ref='evidence:provider:1',
        provider_request_id='request:1',
        observed_at=datetime(2026, 9, 24, tzinfo=UTC),
    )
    validate_provider_response(
        descriptor('yandexgpt', AIProviderKind.CLOUD, free=False),
        request,
        response,
    )


def test_readiness_is_fail_closed() -> None:
    not_ready = AIProviderReadiness(
        provider_id='yandexgpt',
        state=AIProviderReadinessState.NOT_CONFIGURED,
        checked_at=datetime(2026, 9, 24, tzinfo=UTC),
        error_code='missing_runtime_configuration',
    )
    assert not_ready.state is AIProviderReadinessState.NOT_CONFIGURED
    assert not_ready.error_code == 'missing_runtime_configuration'

    with pytest.raises(ValueError, match='ready provider'):
        AIProviderReadiness(
            provider_id='yandexgpt',
            state=AIProviderReadinessState.READY,
            checked_at=datetime(2026, 9, 24, tzinfo=UTC),
            error_code='unexpected',
        )
