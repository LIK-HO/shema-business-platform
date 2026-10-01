from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "RUB"

    def __post_init__(self) -> None:
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("amount must be a valid decimal") from exc

        currency = self.currency.strip().upper()
        if not amount.is_finite():
            raise ValueError("amount must be finite")
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise ValueError("currency must be a 3-letter ASCII code")

        object.__setattr__(
            self,
            "amount",
            amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )
        object.__setattr__(self, "currency", currency)

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
