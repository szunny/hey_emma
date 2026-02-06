import threading
import time

from AppKit import NSSpeechSynthesizer

_synthesizer = None
_lock = threading.Lock()


def _init_synthesizer(voice_name, rate):
    """Initialize the shared NSSpeechSynthesizer (called once)."""
    global _synthesizer
    if _synthesizer is not None:
        return

    _synthesizer = NSSpeechSynthesizer.alloc().init()
    _synthesizer.setRate_(rate)

    # Resolve display name like "Petra (Premium)" to voice identifier
    target = voice_name.split("(")[0].strip().lower()
    quality = voice_name.split("(")[1].rstrip(")").strip().lower() if "(" in voice_name else ""

    voice_id = None
    for vid in NSSpeechSynthesizer.availableVoices():
        attrs = NSSpeechSynthesizer.attributesForVoice_(vid)
        if attrs["VoiceName"].lower() == target:
            if quality and quality in vid.lower():
                voice_id = vid
                break
            if voice_id is None:
                voice_id = vid

    if voice_id:
        _synthesizer.setVoice_(voice_id)
        print(f"TTS Voice: {voice_id}")


def say(text: str, voice: str = "Petra (Premium)", rate: int = 210) -> None:
    """Speak text using macOS NSSpeechSynthesizer (in-process, no subprocess overhead)."""
    with _lock:
        _init_synthesizer(voice, rate)
        _synthesizer.startSpeakingString_(text)
        while _synthesizer.isSpeaking():
            time.sleep(0.02)
