"""Wake-word detector factory.

Selects the backend via the WAKE_WORD_BACKEND environment variable:
- "openwakeword" (default): uses openWakeWord
- "porcupine": uses Picovoice Porcupine

Only the chosen backend is imported (lazy imports).
"""

import os

from emma.wake_word_base import WakeWordInterrupted  # noqa: F401 — re-export

__all__ = ["WakeWordDetector", "WakeWordInterrupted"]


def WakeWordDetector():
    """Create and return a wake-word detector for the configured backend."""
    backend = os.getenv("WAKE_WORD_BACKEND", "openwakeword").lower()

    if backend == "porcupine":
        from emma.wake_word_porcupine import PorcupineWakeWordDetector

        return PorcupineWakeWordDetector()
    else:
        from emma.wake_word_oww import OpenWakeWordDetector

        return OpenWakeWordDetector()
