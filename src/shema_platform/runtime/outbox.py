from __future__ import annotations

from collections.abc import Callable

from shema_platform.application.outbox_router import OutboxHandlerRouter
from shema_platform.application.payment_execution import PaymentExecutionWorkflow
from shema_platform.application.payment_outbox import PaymentOutboxHandler


def build_outbox_router(
    payment_execution: PaymentExecutionWorkflow,
) -> OutboxHandlerRouter:
    """Build the production side-effect router without adding provider logic to the kernel."""
    return OutboxHandlerRouter(
        handlers={
            PaymentOutboxHandler.EVENT_TYPE: PaymentOutboxHandler(
                payment_execution
            )
        }
    )
