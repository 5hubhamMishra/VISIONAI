"""Shared pytest configuration.

Forces Qt's offscreen platform plugin before any PySide6 import can
happen, so GUI tests run correctly in headless environments (CI runners,
this repository's own verification scripts) without a real display.
Does not affect non-GUI tests.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
