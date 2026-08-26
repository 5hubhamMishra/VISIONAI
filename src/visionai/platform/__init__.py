"""Platform-state adapters."""

from visionai.platform.camera import GestureCandidate, LandmarkAdapter, StaticLandmarkAdapter
from visionai.platform.lock_state import (
    LockStateAdapter,
    StaticLockStateAdapter,
    WindowsLockStateAdapter,
)

__all__ = [
    "GestureCandidate",
    "LandmarkAdapter",
    "LockStateAdapter",
    "StaticLandmarkAdapter",
    "StaticLockStateAdapter",
    "WindowsLockStateAdapter",
]
