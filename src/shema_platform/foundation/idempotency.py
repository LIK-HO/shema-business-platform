from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    request_hash: str
    result_ref: str


class IdempotencyStore:
    """Reference contract; production implementation is backed by PostgreSQL."""

    def __init__(self) -> None:
        self._records: dict[str, IdempotencyRecord] = {}

    @staticmethod
    def request_hash(payload: str) -> str:
        return sha256(payload.encode("utf-8")).hexdigest()

    def reserve(self, key: str, request_hash: str, result_ref: str) -> IdempotencyRecord:
        existing = self._records.get(key)
        if existing is not None:
            return existing

        record = IdempotencyRecord(key=key, request_hash=request_hash, result_ref=result_ref)
        self._records[key] = record
        return record

    def get(self, key: str) -> IdempotencyRecord | None:
        return self._records.get(key)
