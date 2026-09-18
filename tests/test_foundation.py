from datetime import UTC, datetime, timedelta

import pytest

from shema_platform.application.commands import Actor, CommandService, CommercialActionCommand
from shema_platform.domain.identity import Identity, IdentityState, Resolution
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import (
    AuthorizationError,
    IdempotencyConflict,
    IntegrityViolation,
    QuarantineRequired,
)
from shema_platform.foundation.evidence import Evidence, TrustLevel, TruthClass
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.outbox import OutboxEvent, OutboxStatus, OutboxStore
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.recovery import RetryPolicy


def authorizer() -> RBACAuthorizer:
    return RBACAuthorizer(
        (
            (
                # Placeholder is intentionally avoided: real subjects are explicit records.
            )
        )
    )
