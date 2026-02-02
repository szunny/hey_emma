"""Porcupine-based wake-word detector."""

import os

import pvporcupine
from pvrecorder import PvRecorder

from emma.config import get_resource_dir
from emma.wake_word_base import BaseWakeWordDetector, WakeWordInterrupted


class PorcupineWakeWordDetector(BaseWakeWordDetector):
    """Porcupine-based wake word detector for 'Hey Emma'."""

    def __init__(self):
        super().__init__()
        access_key = os.getenv("PORCUPINE_ACCESS_KEY")
        resource_dir = get_resource_dir()

        # Model path: env var (absolute) or default in resource dir
        model_path = os.getenv("PORCUPINE_MODEL_PATH")
        if model_path and not os.path.isabs(model_path):
            model_path = str(resource_dir / model_path)

        # Keyword paths: env var or default in resource dir
        keyword_paths_env = os.getenv("PORCUPINE_KEYWORD_PATHS", "")
        keyword_paths = []
        for p in keyword_paths_env.split(","):
            p = p.strip()
            if p and not os.path.isabs(p):
                keyword_paths.append(str(resource_dir / p))
            elif p:
                keyword_paths.append(p)

        sensitivities = [
            float(s) for s in os.getenv("PORCUPINE_SENSITIVITIES", "0.5").split(",")
        ]
        self.keywords = os.getenv("PORCUPINE_KEYWORDS", "Hey-Emma").split(",")

        self.porcupine = pvporcupine.create(
            access_key=access_key,
            model_path=model_path,
            keyword_paths=keyword_paths,
            sensitivities=sensitivities,
        )
        print(f"Porcupine Version: {self.porcupine.version}")

        self.recorder = PvRecorder(
            frame_length=self.porcupine.frame_length,
            device_index=-1,
        )

    def start(self):
        """Start the audio recorder."""
        self._stop_event.clear()
        self.recorder.start()

    def wait_for_wake_word(self) -> str:
        """Block until wake word is detected. Returns the detected keyword.

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
            result = self.porcupine.process(pcm)
            if result >= 0:
                return self.keywords[result]

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
        """Stop recorder and release resources."""
        self.recorder.stop()

    def delete(self):
        """Clean up Porcupine and recorder resources."""
        self._stop_event.set()
        self.recorder.delete()
        self.porcupine.delete()
