"""Platform-state adapters."""

from visionai.platform.lock_state import (
    LockStateAdapter,
    StaticLockStateAdapter,
    WindowsLockStateAdapter,
)

__all__ = ["LockStateAdapter", "StaticLockStateAdapter", "WindowsLockStateAdapter"]
