"""Platform-state adapters.

`visionai.platform.microphone` is deliberately not imported here: it
depends on `numpy`/`sounddevice` (the optional `voice` extra), and this
package's other adapters -- and therefore `visionai.runtime`, which every
entry point uses -- must stay importable for anyone who has not installed
that extra. Import it directly:
`from visionai.platform.microphone import MicrophoneCapture`.
"""

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
