from __future__ import annotations

import os

from shema_platform.adapters.intelligence.opencorporates import (
    OpenCorporatesConfiguration,
    OpenCorporatesProvider,
)
from shema_platform.foundation.configuration import ConfigurationSnapshot


class OpenCorporatesProviderFactory:
    """Explicit, versioned composition boundary for the OpenCorporates provider."""

    FEATURE_FLAG = "intelligence.opencorporates.enabled"

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ConfigurationSnapshot,
        *,
        api_token: str | None = None,
    ) -> OpenCorporatesProvider | None:
        if not snapshot.feature_flags.get(cls.FEATURE_FLAG, False):
            return None

        token = api_token or os.getenv("OPENCORPORATES_API_TOKEN", "").strip()
        if not token:
            raise ValueError(
                "OpenCorporates activation requires OPENCORPORATES_API_TOKEN"
            )

        values = snapshot.values
        configuration = OpenCorporatesConfiguration(
            api_token=token,
            api_version=str(values.get("opencorporates.api_version", "0.4")),
            base_url=str(
                values.get(
                    "opencorporates.base_url",
                    "https://api.opencorporates.com",
                )
            ),
            timeout_seconds=float(
                values.get("opencorporates.timeout_seconds", 5)
            ),
            cost_per_call=float(values.get("opencorporates.cost_per_call", 0)),
            max_requests_per_second=float(
                values.get(
                    "opencorporates.max_requests_per_second",
                    1,
                )
            ),
            coverage=frozenset(
                str(item).strip()
                for item in values.get(
                    "opencorporates.coverage",
                    (
                        "company",
                        "logistics",
                        "construction",
                        "trade",
                    ),
                )
                if str(item).strip()
            ),
            confidence=float(
                values.get("opencorporates.confidence", 0.8)
            ),
        )
        return OpenCorporatesProvider(configuration)
