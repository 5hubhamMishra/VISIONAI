"""Capability registry and manifest contracts."""

from visionai.capabilities.dispatcher import CapabilityHandler, SerializedDispatcher
from visionai.capabilities.manifest import (
    CapabilityManifest,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.capabilities.registry import CapabilityRegistry
from visionai.capabilities.system_info import (
    make_system_date_handler,
    make_system_time_handler,
    system_date_manifest,
    system_info_handlers,
    system_info_manifests,
    system_time_manifest,
)

__all__ = [
    "CapabilityHandler",
    "CapabilityManifest",
    "CapabilityRegistry",
    "IdempotencyMode",
    "ParameterSpec",
    "ParameterType",
    "SerializedDispatcher",
    "make_system_date_handler",
    "make_system_time_handler",
    "system_date_manifest",
    "system_info_handlers",
    "system_info_manifests",
    "system_time_manifest",
]
