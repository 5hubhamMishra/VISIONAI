"""Platform-state adapters.

`visionai.platform.microphone` and `visionai.platform.webcam` are
deliberately not imported here: they depend on `numpy`/`sounddevice` (the
optional `voice` extra) and `opencv-contrib-python`/`mediapipe` (the
optional `vision` extra) respectively, and this package's other adapters
-- and therefore `visionai.runtime`, which every entry point uses -- must
stay importable for anyone who has not installed those extras. Import
them directly: `from visionai.platform.microphone import
MicrophoneCapture`, `from visionai.platform.webcam import
WebcamLandmarkAdapter`.
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
