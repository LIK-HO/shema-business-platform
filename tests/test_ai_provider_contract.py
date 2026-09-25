import pytest

from shema_platform.application.ai_provider import (
    AIProviderDescriptor,
    AIProviderFailure,
    AIProviderFailureCode,
    AIProviderKind,
    AIProviderLimits,
    AIProviderProvenance,
    AIProviderReadiness,
    AIProviderReadinessState,
)


def provider_provenance(**overrides: object) -> AIProviderProvenance:
    values = {
        "source": "https://example.invalid/model",
        "license_name": "Example License",
        "license_url": "https://example.invalid/license",
        "license_checked_at": "2026-09-24",
        "artifact_digest": "sha256:test",
        "runtime": "test-runtime",
        "security_status": "verified",
        "free_commercial_use_verified": True,
    }
    values.update(overrides)
    return AIProviderProvenance(**values)


def limits() -> AIProviderLimits:
    return AIProviderLimits(
        max_request_bytes=32_768,
        max_response_bytes=65_536,
        max_duration_seconds=30,
        max_concurrency=2,
    )


def descriptor(kind: AIProviderKind) -> AIProviderDescriptor:
    return AIProviderDescriptor(
        provider_id="test-provider",
        provider_kind=kind,
        model="test-model",
        model_version="1",
        configuration_version="cfg:v1",
        capabilities=frozenset({"text_generation"}),
        limits=limits(),
        provenance=provider_provenance(),
    )


def test_cloud_descriptor_does_not_require_local_model_license_metadata() -> None:
    result = AIProviderDescriptor(
        provider_id="cloud-test",
        provider_kind=AIProviderKind.CLOUD,
        model="test-cloud-model",
        model_version="1",
        configuration_version="cfg:v1",
        capabilities=frozenset({"text_generation"}),
        limits=limits(),
        provenance=AIProviderProvenance(
            source="https://example.invalid/cloud-api",
            security_status="configured",
        ),
    )

    assert result.provider_kind is AIProviderKind.CLOUD


def test_local_descriptor_requires_free_commercial_use_verification() -> None:
    with pytest.raises(
        ValueError,
        match="verified free commercial use permission",
    ):
        AIProviderDescriptor(
            provider_id="local-test",
            provider_kind=AIProviderKind.LOCAL,
            model="test-local-model",
            model_version="1",
            configuration_version="cfg:v1",
            capabilities=frozenset({"text_generation"}),
            limits=limits(),
            provenance=provider_provenance(
                free_commercial_use_verified=False,
            ),
        )


def test_local_descriptor_requires_provenance_fields() -> None:
    with pytest.raises(
        ValueError,
        match="license, verification, digest and runtime metadata",
    ):
        AIProviderDescriptor(
            provider_id="local-test",
            provider_kind=AIProviderKind.LOCAL,
            model="test-local-model",
            model_version="1",
            configuration_version="cfg:v1",
            capabilities=frozenset({"text_generation"}),
            limits=limits(),
            provenance=provider_provenance(
                artifact_digest=None,
            ),
        )


def test_readiness_state_requires_reason_for_non_ready_provider() -> None:
    with pytest.raises(ValueError, match="requires a reason code"):
        AIProviderReadinessState(AIProviderReadiness.NOT_READY)


def test_ready_provider_cannot_have_failure_reason() -> None:
    with pytest.raises(ValueError, match="cannot carry a failure reason"):
        AIProviderReadinessState(
            AIProviderReadiness.READY,
            "unexpected",
        )


def test_failure_has_typed_code_and_no_retry_surface() -> None:
    failure = AIProviderFailure(
        AIProviderFailureCode.TIMEOUT,
        "bounded execution deadline exceeded",
    )

    assert failure.code is AIProviderFailureCode.TIMEOUT
    assert "retry" not in failure.__dict__
