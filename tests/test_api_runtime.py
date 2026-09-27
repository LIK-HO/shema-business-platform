from fastapi.testclient import TestClient

from shema_platform.application.counterparty_check import (
    CounterpartyCheckResult,
    CounterpartyContradiction,
    FreshnessState,
)
from shema_platform.experience.api import (
    APIApplication,
    RequestContext,
    create_app,
)
from shema_platform.experience.api_models import (
    AIRunRequest,
    AIRunResponse,
    CommercialActionCreateRequest,
    CommercialActionResponse,
    CommunicationResult,