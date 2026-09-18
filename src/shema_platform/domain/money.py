from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "RUB"

    def __post_init__(self) -> None:
        try:
            amount = Decimal(self.amount)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("amount must be a valid decimal") from exc

        if not amount.is_finite():
            raise ValueError("amount must be finite")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency must be a 3-letter code")

        object.__setattr__(
            self,
            "amount",
            amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )
        object.__setattr__(self, "currency", self.currency.upper())

    def add(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def multiply(self, quantity: Decimal) -> Money:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        return Money(self.amount * quantity, self.currency)

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
