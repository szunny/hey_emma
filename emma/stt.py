import time
import threading

import objc
from Foundation import NSLocale, NSRunLoop, NSDate
from Speech import SFSpeechRecognizer, SFSpeechAudioBufferRecognitionRequest
from AVFoundation import AVAudioEngine

# SFSpeechRecognizerAuthorizationStatus constants
_AUTHORIZED = 3  # SFSpeechRecognizerAuthorizationStatusAuthorized


def request_authorization() -> bool:
    """Request speech recognition authorization. Returns True if granted.

    The TCC callback fires on an arbitrary background dispatch queue.
    We use threading.Event for cross-thread synchronization and wrap the
    handler in try/except to prevent Python exceptions from leaking into
    ObjC (which causes SIGABRT on background queues).
    """
    result = [False]
    event = threading.Event()

    def handler(status):
        try:
            result[0] = (int(status) == _AUTHORIZED)
        except Exception:
            result[0] = False
        finally:
            event.set()

    SFSpeechRecognizer.requestAuthorization_(handler)

    if not event.wait(timeout=10.0):
        print("Spracherkennung: Autorisierung Timeout.")
        return False
    return result[0]


def listen(timeout: float = 1.5, prompt: str | None = None) -> str | None:
    """Listen for speech using Apple SFSpeechRecognizer and return transcript.

    Uses AVAudioEngine for microphone input and SFSpeechRecognizer for
    offline German speech recognition. Listens for `timeout` seconds
    after the last speech result update.

    If `prompt` is given, it is spoken (via TTS) after the audio engine is
    prepared but before recording starts — this overlaps STT setup with the
    prompt so the mic is ready the instant the prompt finishes.

    Returns the recognized text or None if nothing was recognized.
    """
    locale = NSLocale.alloc().initWithLocaleIdentifier_("de-DE")
    recognizer = SFSpeechRecognizer.alloc().initWithLocale_(locale)

    if not recognizer.isAvailable():
        print("SFSpeechRecognizer ist nicht verfügbar.")
        return None

    audio_engine = AVAudioEngine.alloc().init()
    request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
    request.setShouldReportPartialResults_(True)

    transcript = [None]
    last_update = [time.time()]
    error_occurred = [False]

    def recognition_handler(result, error):
        if error:
            error_occurred[0] = True
            return
        if result:
            best = result.bestTranscription()
            text = best.formattedString()
            transcript[0] = text
            last_update[0] = time.time()

    task = recognizer.recognitionTaskWithRequest_resultHandler_(
        request, recognition_handler
    )

    input_node = audio_engine.inputNode()
    record_format = input_node.outputFormatForBus_(0)

    def audio_tap(buffer, when):
        request.appendAudioPCMBuffer_(buffer)

    input_node.installTapOnBus_bufferSize_format_block_(0, 1024, record_format, audio_tap)

    audio_engine.prepare()

    # Speak prompt AFTER engine is prepared but BEFORE recording starts.
    # This overlaps STT setup time with the prompt playback.
    if prompt:
        from emma.tts import say
        say(prompt)

    success, err = audio_engine.startAndReturnError_(None)
    if not success:
        print(f"AVAudioEngine konnte nicht gestartet werden: {err}")
        input_node.removeTapOnBus_(0)
        request.endAudio()
        return None

    print("Höre zu...")

    # Wait for speech with timeout after last update
    silence_timeout = timeout
    last_update[0] = time.time()

    try:
        while True:
            # Run the run loop briefly to process audio callbacks
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.1)
            )

            elapsed_since_update = time.time() - last_update[0]

            if error_occurred[0]:
                break

            # If we have a transcript and silence exceeded timeout, stop
            if transcript[0] and elapsed_since_update > silence_timeout:
                break

            # Absolute max listen time (e.g. 15 seconds)
            if elapsed_since_update > 15.0 and not transcript[0]:
                break
    finally:
        audio_engine.stop()
        input_node.removeTapOnBus_(0)
        request.endAudio()

    result = transcript[0]
    if result:
        print(f"Erkannt: '{result}'")
    else:
        print("Nichts erkannt.")
    return result
