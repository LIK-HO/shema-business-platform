import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from shema_platform.application.search_adapter import (
    CompliantSearchAdapter,
    SearchAdapterComplianceError,
    SearchAdapterDescriptor,
    validate_search_adapter,
)
from shema_platform.application.search_planning import SearchSourceRegistry
from shema_platform.application.search_run import SearchSource


ROOT = Path(__file__).parents[1]


@dataclass
class FakeAdapter:
    def search(self, criteria):
        return ()


@dataclass
class InvalidAdapter:
    value: str = "not-searchable"


def registry_source(source_id: str = "fns_transparent_business"):
    payload = json.loads(
        (ROOT / "architecture" / "intelligence_source_registry_contract.json").read_text(
            encoding="utf-8"
        )
    )
    registry = SearchSourceRegistry.from_contract(payload)
    return registry.resolve((source_id,))[0]


def descriptor(source_id: str = "fns_transparent_business", **overrides):
    source = registry_source(source_id)
    values = {
        "source_id": source.source_id,
        "source_class": source.source_class,
        "reliability": source.reliability,
        "access_mode": source.access_mode,
        "network_execution_enabled": False,
        "lawful_access_confirmed": True,
    }
    values.update(overrides)
    return SearchAdapterDescriptor(**values)


def test_compliance_contract_is_network_disabled_and_not_ranking_authority() -> None:
    payload = json.loads(
        (ROOT / "architecture" / "search_adapter_compliance_contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["network_execution_enabled"] is False
    assert payload["ranking_authority"] is False
    assert "adapter_exposes_callable_search" in payload["required_checks"]


def test_valid_adapter_is_compliant_without_executing_it() -> None:
    adapter = FakeAdapter()
    source = registry_source()
    spec = descriptor()
    validate_search_adapter(
        source,
        spec,
        adapter,
        lawful_access_required=True,
    )
    assert isinstance(
        CompliantSearchAdapter(
            source=source,
            descriptor=spec,
            adapter=adapter,
        ).search_source(),
        SearchSource,
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_id", "primary_company_site", "source_id"),
        ("source_class", "primary_company", "source_class"),
        ("reliability", "primary", "reliability"),
        ("access_mode", "approved_adapter_only", "access_mode"),
    ],
)
def test_descriptor_must_match_registry_metadata(field, value, message) -> None:
    source = registry_source()
    kwargs = {
        "source_id": source.source_id,
        "source_class": source.source_class,
        "reliability": source.reliability,
        "access_mode": source.access_mode,
        "lawful_access_confirmed": True,
    }
    kwargs[field] = value
    spec = SearchAdapterDescriptor(**kwargs)
    with pytest.raises(SearchAdapterComplianceError, match=message):
        validate_search_adapter(
            source,
            spec,
            FakeAdapter(),
            lawful_access_required=True,
        )


def test_descriptor_network_execution_is_rejected() -> None:
    with pytest.raises(
        SearchAdapterComplianceError,
        match="network execution must remain disabled",
    ):
        validate_search_adapter(
            registry_source(),
            descriptor(network_execution_enabled=True),
            FakeAdapter(),
            lawful_access_required=True,
        )


def test_registry_source_network_automation_is_rejected() -> None:
    source = registry_source()
    bad_source = type(source)(
        source_id=source.source_id,
        name=source.name,
        source_class=source.source_class,
        reliability=source.reliability,
        access_mode=source.access_mode,
        network_automation=True,
    )
    with pytest.raises(
        SearchAdapterComplianceError,
        match="cannot permit network automation",
    ):
        validate_search_adapter(
            bad_source,
            descriptor(),
            FakeAdapter(),
            lawful_access_required=True,
        )


def test_lawful_access_must_be_explicitly_confirmed() -> None:
    with pytest.raises(
        SearchAdapterComplianceError,
        match="lawful access must be explicitly confirmed",
    ):
        validate_search_adapter(
            registry_source(),
            descriptor(lawful_access_confirmed=False),
            FakeAdapter(),
            lawful_access_required=True,
        )


def test_search_method_is_required() -> None:
    with pytest.raises(
        SearchAdapterComplianceError,
        match="callable search method",
    ):
        validate_search_adapter(
            registry_source(),
            descriptor(),
            InvalidAdapter(),
            lawful_access_required=True,
        )


def test_lawful_access_requirement_can_be_disabled_explicitly() -> None:
    validate_search_adapter(
        registry_source(),
        descriptor(lawful_access_confirmed=False),
        FakeAdapter(),
        lawful_access_required=False,
    )


def test_descriptor_rejects_blank_identity_fields() -> None:
    with pytest.raises(SearchAdapterComplianceError, match="source_id"):
        SearchAdapterDescriptor(
            source_id="",
            source_class="official_registry",
            reliability="authoritative",
            access_mode="manual_operator_lookup",
        )
