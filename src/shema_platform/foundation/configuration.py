from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshot:
    """Versioned operational configuration; business policy remains separate."""

    version: str
    environment: str
    values: Mapping[str, Any]
    feature_flags: Mapping[str, bool]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("configuration version is required")
        if not self.environment.strip():
            raise ValueError("environment is required")
        if any(not key.strip() for key in self.values):
            raise ValueError("configuration keys cannot be empty")
        if any(not key.strip() for key in self.feature_flags):
            raise ValueError("feature flag names cannot be empty")

        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "feature_flags", MappingProxyType(dict(self.feature_flags)))


class ConfigurationRegistry:
    """Explicit version registry with one active snapshot."""

    def __init__(self) -> None:
        self._versions: dict[str, ConfigurationSnapshot] = {}
        self._active_version: str | None = None

    def register(self, snapshot: ConfigurationSnapshot) -> None:
        existing = self._versions.get(snapshot.version)
        if existing is not None and existing != snapshot:
            raise ValueError("configuration version collision")
        self._versions[snapshot.version] = snapshot

    def activate(self, version: str) -> ConfigurationSnapshot:
        snapshot = self._versions.get(version)
        if snapshot is None:
            raise KeyError(f"unknown configuration version: {version}")
        self._active_version = version
        return snapshot

    def active(self) -> ConfigurationSnapshot:
        if self._active_version is None:
            raise RuntimeError("no active configuration")
        return self._versions[self._active_version]
