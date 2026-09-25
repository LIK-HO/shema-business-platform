from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from shema_platform.application.ai_runtime import (
    AIExecutionTrust,
    AIExecutionTrustResolver,
)
from shema_platform.foundation.errors import QuarantineRequired
from shema_platform.platform.postgres import DBConnection


@dataclass(frozen=True, slots=True)
class PostgresAIExecutionTrustResolver(AIExecutionTrustResolver):
    """Derives AI trust inputs from canonical PostgreSQL state."""

    connection_factory: Callable[[], DBConnection]

    def resolve(
        self,
        *,
        resource_ref: str,
        evidence_refs: tuple[str, ...],
    ) -> AIExecutionTrust:
        connection = self.connection_factory()
        try:
            resource_trust = self._resource_trust(connection, resource_ref)
            evidence_level = self._evidence_level(
                connection,
                resource_ref,
                evidence_refs,
            )
            return AIExecutionTrust(
                resource_trust_level=resource_trust,
                evidence_level=evidence_level,
            )
        finally:
            connection.close()

    @staticmethod
    def _resource_trust(
        connection: DBConnection,
        resource_ref: str,
    ) -> int:
        row = connection.execute(
            """
            select state
            from identity
            where identity_id::text = %s
            """,
            (resource_ref,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown AI resource: {resource_ref}")

        return {
            "identified": 1,
            "verified": 2,
            "active": 2,
        }.get(str(row[0]), 0)

    @staticmethod
    def _evidence_level(
        connection: DBConnection,
        resource_ref: str,
        evidence_refs: tuple[str, ...],
    ) -> int:
        if not evidence_refs:
            return 0

        placeholders = ", ".join(["%s"] * len(evidence_refs))
        rows = connection.execute(
            f"""
            select evidence_id::text, subject_ref, trust_level, lifecycle, expires_at
            from evidence
            where evidence_id::text in ({placeholders})
            """,
            evidence_refs,
        ).fetchall()

        records: dict[str, tuple[Any, ...]] = {
            str(row[0]): row for row in rows
        }
        if len(records) != len(evidence_refs):
            raise QuarantineRequired(
                "AI execution references missing evidence"
            )

        levels: list[int] = []
        for evidence_ref in evidence_refs:
            row = records[evidence_ref]
            _, subject_ref, trust_level, lifecycle, expires_at = row
            if str(subject_ref) != resource_ref:
                raise QuarantineRequired(
                    "AI execution evidence does not belong to the requested resource"
                )
            if str(lifecycle) != "active":
                raise QuarantineRequired(
                    "AI execution evidence is not active"
                )
            if expires_at is not None:
                now = connection.execute("select now()").fetchone()
                if now is None or now[0] >= expires_at:
                    raise QuarantineRequired(
                        "AI execution evidence is expired"
                    )

            level = str(trust_level)
            if not level.startswith("T") or not level[1:].isdigit():
                raise QuarantineRequired(
                    "AI execution evidence has an invalid trust level"
                )
            levels.append(int(level[1:]))

        return min(levels)
