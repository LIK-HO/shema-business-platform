from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable


class DiagnosticStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    check_id: str
    status: DiagnosticStatus
    message: str


class Diagnostics:
    """Deterministic internal reconciliation/check framework."""

    def run(self, checks: dict[str, Callable[[], DiagnosticResult]]) -> tuple[DiagnosticResult, ...]:
        results: list[DiagnosticResult] = []
        for check_id, check in checks.items():
            result = check()
            if result.check_id != check_id:
                raise ValueError("diagnostic returned mismatched check_id")
            results.append(result)
        return tuple(results)

    @staticmethod
    def healthy(results: tuple[DiagnosticResult, ...]) -> bool:
        return all(result.status is not DiagnosticStatus.FAIL for result in results)
