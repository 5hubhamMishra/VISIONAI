"""Capability registry and manifest contracts."""

from visionai.capabilities.applications import (
    ALLOWED_APPLICATIONS,
    app_open_manifest,
    make_app_open_handler,
)
from visionai.capabilities.dispatcher import CapabilityHandler, SerializedDispatcher
from visionai.capabilities.manifest import (
    CapabilityManifest,
    IdempotencyMode,
    ParameterSpec,
    ParameterType,
)
from visionai.capabilities.meta import (
    make_system_capabilities_handler,
    make_system_help_handler,
    meta_handlers,
    meta_manifests,
    system_capabilities_manifest,
    system_help_manifest,
)
from visionai.capabilities.registry import CapabilityRegistry
from visionai.capabilities.system_info import (
    make_system_battery_handler,
    make_system_date_handler,
    make_system_health_handler,
    make_system_time_handler,
    system_battery_manifest,
    system_date_manifest,
    system_health_manifest,
    system_info_handlers,
    system_info_manifests,
    system_time_manifest,
)

__all__ = [
    "ALLOWED_APPLICATIONS",
    "CapabilityHandler",
    "CapabilityManifest",
    "CapabilityRegistry",
    "IdempotencyMode",
    "ParameterSpec",
    "ParameterType",
    "SerializedDispatcher",
    "app_open_manifest",
    "make_app_open_handler",
    "make_system_battery_handler",
    "make_system_capabilities_handler",
    "make_system_date_handler",
    "make_system_health_handler",
    "make_system_help_handler",
    "make_system_time_handler",
    "meta_handlers",
    "meta_manifests",
    "system_battery_manifest",
    "system_capabilities_manifest",
    "system_date_manifest",
    "system_health_manifest",
    "system_help_manifest",
    "system_info_handlers",
    "system_info_manifests",
    "system_time_manifest",
]
