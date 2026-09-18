from __future__ import annotations

import json

from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.search import SearchHit
from shema_platform.application.ports import IdentityRepository, QuarantineRepository
from shema_platform.platform.postgres import DBConnection


class PostgresIdentityRepository(IdentityRepository):
    """Thin persistence adapter; it performs no identity resolution."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def find_by_tax_id(self, tax_id: str) -> Identity | None:
        cursor = self._connection.execute(
            """
            select identity_id, canonical_name, state, tax_id, registration_id
            from identity
            where tax_id = %s
            """,
            (tax_id.strip(),),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        identity_id, canonical_name, state, stored_tax_id, registration_id = row
        return Identity(
            identity_id=str(identity_id),
            canonical_name=str(canonical_name),
            state=IdentityState(str(state)),
            tax_id=str(stored_tax_id) if stored_tax_id is not None else None,
            registration_id=str(registration_id) if registration_id is not None else None,
        )

    def add(self, identity: Identity) -> None:
        self._connection.execute(
            """
            insert into identity (
                identity_id,
                canonical_name,
                state,
                tax_id,
                registration_id
            )
            values (%s, %s, %s, %s, %s)
            """,
            (
                identity.identity_id,
                identity.canonical_name,
                identity.state.value,
                identity.tax_id,
                identity.registration_id,
            ),
        )


class PostgresQuarantineRepository(QuarantineRepository):
    """Persists quarantine facts without resolving or mutating business truth."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(
        self,
        *,
        object_type: str,
        object_ref: str,
        reason_code: str,
        payload: dict[str, object],
    ) -> None:
        self._connection.execute(
            """
            insert into quarantine_record (
                quarantine_id,
                object_type,
                object_ref,
                reason_code,
                payload
            )
            values (gen_random_uuid(), %s, %s, %s, %s::jsonb)
            """,
            (
                object_type,
                object_ref,
                reason_code,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
