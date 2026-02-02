"""openWakeWord-based wake-word detector."""

import os

import numpy as np
from openwakeword.model import Model
from pvrecorder import PvRecorder

from emma.wake_word_base import BaseWakeWordDetector, WakeWordInterrupted


class OpenWakeWordDetector(BaseWakeWordDetector):
    """openWakeWord-based wake word detector.

    Uses a built-in or custom ONNX model for wake-word detection.
    Audio is captured via PvRecorder at 16 kHz with 1280-sample frames (80 ms).
    """

    def __init__(self):
        super().__init__()

        model_path = os.getenv("OPENWAKEWORD_MODEL_PATH", "")
        model_names = os.getenv("OPENWAKEWORD_MODEL_NAMES", "hey_jarvis")
        self.threshold = float(os.getenv("OPENWAKEWORD_THRESHOLD", "0.5"))
        self.keyword = os.getenv("OPENWAKEWORD_KEYWORD", "Hey-Emma")

        if model_path:
            self.model = Model(
                wakeword_models=[model_path],
                inference_framework="onnx",
            )
        else:
            self.model = Model(
                wakeword_models=[n.strip() for n in model_names.split(",")],
                inference_framework="onnx",
            )

        print(f"openWakeWord models: {list(self.model.models.keys())}")

        self.recorder = PvRecorder(
            frame_length=1280,
            device_index=-1,
        )

    def start(self):
        """Start the audio recorder and reset model state."""
        self._stop_event.clear()
        self.model.reset()
        self.recorder.start()

    def wait_for_wake_word(self) -> str:
        """Block until wake word is detected. Returns the keyword string.

        Raises WakeWordInterrupted if interrupt() is called while waiting.
        """
        while True:
            if self._stop_event.is_set():
                raise WakeWordInterrupted()
            try:
                pcm = self.recorder.read()
            except Exception:
                if self._stop_event.is_set():
                    raise WakeWordInterrupted()
                raise

            audio = np.array(pcm, dtype=np.int16)
            prediction = self.model.predict(audio)

            for model_name, score in prediction.items():
                if score >= self.threshold:
                    self.model.reset()
                    return self.keyword

    def interrupt(self):
        """Interrupt a blocking wait_for_wake_word() call.

        Sets the stop event and stops the recorder so that read() unblocks.
        """
        self._stop_event.set()
        try:
            self.recorder.stop()
        except Exception:
            pass

    def stop(self):
        """Stop the audio recorder."""
        self.recorder.stop()

    def delete(self):
        """Clean up recorder resources."""
        self._stop_event.set()
        self.recorder.delete()
