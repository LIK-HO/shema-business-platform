from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from shema_platform.adapters.ai.application_composition import (
    YandexGPTApplicationComposition,
)
from shema_platform.adapters.intelligence.dadata import DaDataConfiguration
from shema_platform.adapters.intelligence.dadata_activation import (
    DaDataActivationReadiness,
    DaDataControlledActivationGate,
)
from shema_platform.application.ai_runtime import AIExecutionTrustResolver
from shema_platform.application.counterparty_lookup import CounterpartyLookupProvider
from shema_platform.application.counterparty_provider_activation import (
    CounterpartyProviderActivationService,
)
from shema_platform.application.counterparty_provider_evidence import (
    CounterpartyProviderEvidenceService,
)
from shema_platform.application.counterparty_provider_runtime_lookup import (
    CounterpartyProviderRuntimeLookupService,
)
from shema_platform.application.ports import UnitOfWork
from shema_platform.application.public_intake import PublicIntakeService
from shema_platform.application.public_preflight import (
    PublicCounterpartyPreflightService,
)
from shema_platform.experience.ai_application import AIOnlyAPIApplication
from shema_platform.experience.api import APIApplication, create_app
from shema_platform.experience.search_composition import SearchAugmentedAPIApplication
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.http_security import BotChallengeVerifier
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.provider_activation import ProviderActivationStateStore
from shema_platform.foundation.telemetry import TelemetrySink
from shema_platform.platform.public_intake_postgres import (
    PostgresOperatorNotificationReader,
    PostgresPublicIntakeRepository,
    PostgresPublicRequestProjection,
)


@dataclass(frozen=True, slots=True)
class PublicIntakeRuntimeAssembly:
    """Bounded public-intake runtime; raw intake stays in its own database."""

    service: PublicIntakeService
    notification_reader: PostgresOperatorNotificationReader
    bot_challenge_verifier: BotChallengeVerifier

    def create_http_app(
        self,
        *,
        application: APIApplication | None = None,
        authenticator=None,
        enable_docs: bool = True,
        telemetry: TelemetrySink | None = None,
        provider_health=None,
    ):
        return create_app(
            application=application,
            authenticator=authenticator,
            enable_docs=enable_docs,
            telemetry=telemetry,
            provider_health=provider_health,
            public_intake=self.service,
            operator_notification_reader=self.notification_reader,
            bot_challenge_verifier=self.bot_challenge_verifier,
        )


def compose_public_intake_runtime(
    *,
    intake_connection_factory: Callable,
    shema_unit_of_work_factory: Callable[[], UnitOfWork],
    counterparty_provider: CounterpartyLookupProvider | None = None,
    allowed_origins: frozenset[str] = frozenset(),
    bot_challenge_verifier: BotChallengeVerifier | None = None,
    submission_limit: int = 5,
    lookup_limit: int = 20,
    window_seconds: int = 600,
    telemetry: TelemetrySink | None = None,
    provider_sleeper: Callable[[float], None] | None = None,
) -> PublicIntakeRuntimeAssembly:
    if not allowed_origins:
        raise ValueError("public intake requires a non-empty origin allowlist")
    if bot_challenge_verifier is None:
        raise ValueError("public intake requires a server-side bot challenge verifier")

    def repository_factory():
        return PostgresPublicIntakeRepository(intake_connection_factory)

    def cache_lookup(cache_key: str, now):
        with repository_factory() as repository:
            return repository.get_preflight_cache(cache_key, now=now)

    def consume_lookup_budget(public_client_key: str, now):
        with repository_factory() as repository:
            repository.consume_budget(
                public_client_key=public_client_key,
                budget="registry_lookup",
                limit=lookup_limit,
                window_seconds=window_seconds,
                now=now,
            )

    def cache_store(cache_key: str, snapshot):
        with repository_factory() as repository:
            repository.save_preflight_cache(cache_key, snapshot)

    preflight = PublicCounterpartyPreflightService(
        provider=counterparty_provider,
        cache_lookup=cache_lookup,
        consume_lookup_budget=consume_lookup_budget,
        cache_store=cache_store,
        sleeper=provider_sleeper,
    )
    projector = PostgresPublicRequestProjection(shema_unit_of_work_factory)
    service = PublicIntakeService(
        repository_factory,
        preflight=preflight,
        projector=projector,
        submission_limit=submission_limit,
        lookup_limit=lookup_limit,
        window_seconds=window_seconds,
        require_bot_challenge=True,
        enforce_edge_proof=True,
        allowed_origins=allowed_origins,
    )
    reader = PostgresOperatorNotificationReader(
        lambda: intake_connection_factory(),
    )
    return PublicIntakeRuntimeAssembly(
        service=service,
        notification_reader=reader,
        bot_challenge_verifier=bot_challenge_verifier,
    )


@dataclass(frozen=True, slots=True)
class YandexGPTRuntimeAssembly:
    """Explicit composition root; construction never activates provider traffic."""

    ai: YandexGPTApplicationComposition

    def api_application(
        self,
        *,
        search_application: APIApplication | None = None,
    ) -> APIApplication:
        base = AIOnlyAPIApplication(self.ai.service())
        if search_application is None:
            return base
        return SearchAugmentedAPIApplication(base, search_application)

    def create_http_app(
        self,
        *,
        authenticator=None,
        enable_docs: bool = True,
        telemetry: TelemetrySink | None = None,
        search_application: APIApplication | None = None,
    ):
        return create_app(
            application=self.api_application(search_application=search_application),
            authenticator=authenticator,
            enable_docs=enable_docs,
            telemetry=telemetry,
        )

    def activate_yandexgpt(
        self,
        *,
        activated_by: str,
        api_key: str | None = None,
    ) -> None:
        self.ai.activate(
            activated_by=activated_by,
            api_key=api_key,
        )

    def rollback_yandexgpt(
        self,
        *,
        rolled_back_by: str,
        reason: str,
    ) -> None:
        self.ai.rollback(
            rolled_back_by=rolled_back_by,
            reason=reason,
        )



@dataclass(frozen=True, slots=True)
class CounterpartyProviderRuntimeAssembly:
    """Explicit counterparty-provider runtime composition; traffic stays gated."""

    activation: CounterpartyProviderActivationService
    lookup: CounterpartyProviderRuntimeLookupService | None = None

    def create_http_app(
        self,
        *,
        application: APIApplication | None = None,
        authenticator=None,
        enable_docs: bool = True,
        telemetry: TelemetrySink | None = None,
    ):
        return create_app(
            application=application,
            authenticator=authenticator,
            enable_docs=enable_docs,
            telemetry=telemetry,
            counterparty_provider_activation=self.activation,
            counterparty_provider_lookup=self.lookup,
        )

    def provider(self):
        return self.activation.provider()


def compose_yandexgpt_runtime(
    *,
    snapshot: ConfigurationSnapshot,
    telemetry: TelemetrySink,
    unit_of_work_factory: Callable[[], UnitOfWork],
    trust_resolver: AIExecutionTrustResolver,
    prompt_renderer: Callable,
    cost_estimator: Callable[[int, int], float],
    policy: PolicyEngine | None = None,
    activation_state_store: ProviderActivationStateStore | None = None,
) -> YandexGPTRuntimeAssembly:
    """Build the explicit runtime assembly without activating YandexGPT."""
    return YandexGPTRuntimeAssembly(
        ai=YandexGPTApplicationComposition(
            snapshot=snapshot,
            telemetry=telemetry,
            unit_of_work_factory=unit_of_work_factory,
            trust_resolver=trust_resolver,
            prompt_renderer=prompt_renderer,
            cost_estimator=cost_estimator,
            policy=policy,
            activation_state_store=activation_state_store,
        )
    )



def compose_counterparty_provider_runtime(
    *,
    configuration: DaDataConfiguration,
    readiness: DaDataActivationReadiness,
    telemetry: TelemetrySink,
    provider_factory: Callable[[DaDataConfiguration], CounterpartyLookupProvider] | None = None,
    unit_of_work_factory: Callable[[], UnitOfWork] | None = None,
    max_attempts: int = 3,
    backoff_seconds: float = 0.25,
    sleeper: Callable[[float], None] | None = None,
) -> CounterpartyProviderRuntimeAssembly:
    """Compose the control-plane without activating or connecting to DaData."""
    gate = DaDataControlledActivationGate(
        telemetry=telemetry,
        provider_factory=provider_factory,
    )
    activation = CounterpartyProviderActivationService(
        gate=gate,
        configuration=configuration,
        readiness=readiness,
    )
    lookup = None
    if unit_of_work_factory is not None:
        lookup = CounterpartyProviderRuntimeLookupService(
            provider_id="dadata_organization_api",
            provider_resolver=gate.provider,
            evidence_service=CounterpartyProviderEvidenceService(unit_of_work_factory),
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            sleeper=sleeper,
        )
    return CounterpartyProviderRuntimeAssembly(
        activation=activation,
        lookup=lookup,
    )
