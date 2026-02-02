"""Base class and shared exception for wake-word detectors."""

import threading
from abc import ABC, abstractmethod


class WakeWordInterrupted(Exception):
    """Raised when wake word detection is interrupted via interrupt()."""


class BaseWakeWordDetector(ABC):
    """Abstract base class for wake-word detector backends."""

    def __init__(self):
        self._stop_event = threading.Event()

    @abstractmethod
    def start(self):
        """Start the audio recorder and prepare for detection."""

    @abstractmethod
    def wait_for_wake_word(self) -> str:
        """Block until a wake word is detected.

        Returns the detected keyword string.
        Raises WakeWordInterrupted if interrupt() is called while waiting.
        """

    @abstractmethod
    def stop(self):
        """Stop the audio recorder."""

    @abstractmethod
    def interrupt(self):
        """Interrupt a blocking wait_for_wake_word() call."""

    @abstractmethod
    def delete(self):
        """Clean up all resources."""
