"""In-memory capability registry."""

from __future__ import annotations

from collections.abc import Iterable

from visionai.capabilities.manifest import CapabilityManifest
from visionai.core.errors import CapabilityError, UnregisteredCapabilityError
from visionai.core.events import RiskLevel


class CapabilityRegistry:
    """Stores reviewed capability manifests by stable ID."""

    def __init__(self, manifests: Iterable[CapabilityManifest] = ()) -> None:
        self._manifests: dict[str, CapabilityManifest] = {}
        for manifest in manifests:
            self.register(manifest)

    def register(self, manifest: CapabilityManifest) -> None:
        if manifest.risk_level == RiskLevel.PROHIBITED:
            raise CapabilityError("prohibited capabilities cannot be registered")
        if manifest.id in self._manifests:
            raise CapabilityError(f"capability already registered: {manifest.id}")
        self._manifests[manifest.id] = manifest

    def get(self, capability_id: str) -> CapabilityManifest:
        try:
            return self._manifests[capability_id]
        except KeyError as exc:
            raise UnregisteredCapabilityError(f"unregistered capability: {capability_id}") from exc

    def contains(self, capability_id: str) -> bool:
        return capability_id in self._manifests

    def list(self) -> tuple[CapabilityManifest, ...]:
        return tuple(self._manifests.values())
