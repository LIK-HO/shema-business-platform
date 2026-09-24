from __future__ import annotations

import os

from shema_platform.adapters.ai.openai import (
    EvidenceResolver,
    OpenAIConfiguration,
    OpenAIProvider,
    PromptResolver,
)
from shema_platform.foundation.configuration import ConfigurationSnapshot


class OpenAIProviderFactory:
    """Explicit, versioned composition boundary for the concrete OpenAI provider."""

    FEATURE_FLAG = "ai.openai.enabled"

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ConfigurationSnapshot,
        *,
        api_key: str | None = None,
        prompt_resolver: PromptResolver | None = None,
        evidence_resolver: EvidenceResolver | None = None,
    ) -> OpenAIProvider | None:
        if not snapshot.feature_flags.get(cls.FEATURE_FLAG, False):
            return None

        token = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        if not token:
            raise ValueError("OpenAI activation requires OPENAI_API_KEY")
        if prompt_resolver is None:
            raise ValueError("OpenAI activation requires prompt_resolver")
        if evidence_resolver is None:
            raise ValueError("OpenAI activation requires evidence_resolver")

        values = snapshot.values
        configuration = OpenAIConfiguration(
            api_key=token,
            model=str(values.get("openai.model", "gpt-6-luna")),
            timeout_seconds=float(
                values.get("openai.timeout_seconds", 15)
            ),
            max_input_chars=int(
                values.get("openai.max_input_chars", 32_768)
            ),
            max_output_tokens=int(
                values.get("openai.max_output_tokens", 4_096)
            ),
            max_response_bytes=int(
                values.get("openai.max_response_bytes", 1_048_576)
            ),
            max_request_body_bytes=int(
                values.get("openai.max_request_body_bytes", 262_144)
            ),
            max_output_chars=int(
                values.get("openai.max_output_chars", 65_536)
            ),
            max_requests_per_second=float(
                values.get("openai.max_requests_per_second", 2)
            ),
            max_cost_usd_per_call=float(
                values.get("openai.max_cost_usd_per_call", 0.05)
            ),
            input_cost_per_million_tokens=float(
                values.get("openai.input_cost_per_million", 0.10)
            ),
            output_cost_per_million_tokens=float(
                values.get("openai.output_cost_per_million", 0.50)
            ),
        )
        return OpenAIProvider(
            configuration,
            prompt_resolver=prompt_resolver,
            evidence_resolver=evidence_resolver,
        )
