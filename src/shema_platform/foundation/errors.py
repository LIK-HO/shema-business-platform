class DomainError(Exception):
    """Base class for expected business/domain violations."""


class AuthorizationError(DomainError):
    pass


class PolicyDenied(DomainError):
    pass


class IntegrityViolation(DomainError):
    pass


class IdempotencyConflict(DomainError):
    pass


class QuarantineRequired(DomainError):
    pass
