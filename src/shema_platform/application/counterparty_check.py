from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import uuid4

from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.evidence import (
    Evidence,
    EvidenceLifecycle,
    TrustLevel,
    TruthClass,