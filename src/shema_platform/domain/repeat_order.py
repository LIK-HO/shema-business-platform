from __future__ import annotations

import calendar
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class RepeatPlanStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class RepeatCadenceUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass(frozen=True, slots=True)
class RepeatCadence:
    unit: RepeatCadenceUnit
    interval: int = 1

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise ValueError("repeat cadence interval must be >= 1")

    def next_after(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("repeat schedule timestamps must be timezone-aware")

        if self.unit is RepeatCadenceUnit.DAY:
            return value + timedelta(days=self.interval)
        if self.unit is RepeatCadenceUnit.WEEK:
            return value + timedelta(weeks=self.interval)

        month_index = value.month - 1 + self.interval
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)


@dataclass(frozen=True, slots=True)
class RepeatOrderContext:
    scheduled_for: datetime
    service_scope: str
    capacity_units: Decimal

    def __post_init__(self) -> None:
        if self.scheduled_for.tzinfo is None:
            raise ValueError("scheduled_for must be timezone-aware")
        if not self.service_scope.strip():
            raise ValueError("service_scope is required")
        if self.capacity_units <= 0:
            raise ValueError("capacity_units must be positive")


@dataclass(frozen=True, slots=True)
class RepeatOrderPlan:
    plan_id: str
    source_order_id: str
    identity_id: str
    cadence: RepeatCadence
    context: RepeatOrderContext
    status: RepeatPlanStatus = RepeatPlanStatus.ACTIVE
    last_order_id: str | None = None
    pending_order_id: str | None = None
    skipped_occurrences: int = 0
    revision: int = 1

    def __post_init__(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id is required")
        if not self.source_order_id.strip():
            raise ValueError("source_order_id is required")
        if not self.identity_id.strip():
            raise ValueError("identity_id is required")
        if self.skipped_occurrences < 0:
            raise ValueError("skipped_occurrences cannot be negative")
        if self.revision < 1:
            raise ValueError("repeat plan revision must be >= 1")

    def pause(self) -> RepeatOrderPlan:
        if self.status is not RepeatPlanStatus.ACTIVE:
            raise ValueError("only active repeat plan can be paused")
        return replace(self, status=RepeatPlanStatus.PAUSED)

    def resume(self) -> RepeatOrderPlan:
        if self.status is not RepeatPlanStatus.PAUSED:
            raise ValueError("only paused repeat plan can be resumed")
        return replace(self, status=RepeatPlanStatus.ACTIVE)

    def skip_once(self) -> RepeatOrderPlan:
        if self.status is not RepeatPlanStatus.ACTIVE:
            raise ValueError("only active repeat plan can skip an occurrence")
        if self.pending_order_id is not None:
            raise ValueError("cannot skip while a repeat order is pending")
        return replace(
            self,
            context=replace(
                self.context,
                scheduled_for=self.cadence.next_after(self.context.scheduled_for),
            ),
            skipped_occurrences=self.skipped_occurrences + 1,
        )

    def cancel(self) -> RepeatOrderPlan:
        if self.status is RepeatPlanStatus.CANCELLED:
            raise ValueError("repeat plan is already cancelled")
        return replace(self, status=RepeatPlanStatus.CANCELLED)

    def edit_context(self, context: RepeatOrderContext) -> RepeatOrderPlan:
        if self.status is RepeatPlanStatus.CANCELLED:
            raise ValueError("cancelled repeat plan cannot be edited")
        if self.pending_order_id is not None:
            raise ValueError("cannot edit repeat context while an order is pending")
        return replace(self, context=context)

    def attach_pending_order(self, order_id: str) -> RepeatOrderPlan:
        if not order_id.strip():
            raise ValueError("pending order id is required")
        if self.status is RepeatPlanStatus.CANCELLED:
            raise ValueError("cancelled repeat plan cannot create a pending order")
        if self.pending_order_id is not None:
            raise ValueError("repeat plan already has a pending order")
        return replace(self, pending_order_id=order_id)

    def mark_order_confirmed(self, order_id: str) -> RepeatOrderPlan:
        if self.pending_order_id != order_id:
            raise ValueError("confirmed order does not match the pending repeat order")
        next_context = self.context
        if self.status is RepeatPlanStatus.ACTIVE:
            next_context = replace(
                self.context,
                scheduled_for=self.cadence.next_after(self.context.scheduled_for),
            )
        return replace(
            self,
            context=next_context,
            last_order_id=order_id,
            pending_order_id=None,
        )
