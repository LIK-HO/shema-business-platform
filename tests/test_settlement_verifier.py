from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from dataclasses import dataclass

import pytest

from shema_platform.application.settlement_execution import (
    SettlementProviderAdapter,
    SettlementStatementVerifier,
)
from shema_platform.domain.money import Money
from shema_platform.domain.settlement import (
    SettlementLine,
    SettlementStatement,
)
from shema_platform.foundation.errors import IntegrityViolation


@dataclass
class FakeSettlementAdapter(SettlementProviderAdapter):
    provider_name: str = "test-settlement"
    statement_hash: str = ""

    def verify_settlement_statement(
        self,
        *,
        headers: Mapping[str, str],
        payload: bytes,
    ) -> SettlementStatement:
        return SettlementStatement(
            statement_id="statement-1",
            provider_settlement_ref="provider-settlement-1",
            statement_hash=self.statement_hash,
            lines=(
                SettlementLine(
                    line_id="line-1",
                    settlement_id="settlement-1",
                    provider_ref="provider-payment-1",
                    amount=Money(6000, "RUB"),
                    statement_ref="statement-1",
                ),
            ),
            gross=Money(6000, "RUB"),
            fees=Money(150, "RUB"),
            net=Money(5850, "RUB"),
            settled_at=datetime.now(UTC),
        )


def test_settlement_statement_verifier_binds_hash_to_payload() -> None:
    payload = b"settlement-statement"
    adapter = FakeSettlementAdapter(statement_hash=sha256(payload).hexdigest())
    verifier = SettlementStatementVerifier(adapter)

    statement = verifier.verify(headers={}, payload=payload)

    assert statement.statement_hash == sha256(payload).hexdigest()


def test_settlement_statement_verifier_rejects_tampered_hash() -> None:
    adapter = FakeSettlementAdapter(statement_hash="tampered")
    verifier = SettlementStatementVerifier(adapter)

    with pytest.raises(
        IntegrityViolation,
        match="does not match received payload",
    ):
        verifier.verify(headers={}, payload=b"settlement-statement")
