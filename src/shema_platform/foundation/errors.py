class DomainError(Exception):
    """Base class for expected business/domain violations."""


class AuthorizationError(DomainError):
    """Actor is not authorized to execute the requested command."""


class PolicyDenied(DomainError):
    """A domain/application policy rejected an operation."""


class IntegrityViolation(DomainError):
    """State or data integrity invariant was violated."""


class IdempotencyConflict(DomainError):
    """An idempotency key was reused for a different request."""


class ExternalEffectUnknown(DomainError):
    """The outcome of an external effect is unknown and must not be replayed automatically."""


class QuarantineRequired(DomainError):
    """The subject is too uncertain for a critical operation."""
