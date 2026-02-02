"""Hey Emma — macOS Menubar App.

Runs the wake-word / STT / command loop on a background thread
and exposes Start/Stop + Start at Login via a status-bar menu.
"""

import random
import threading
import warnings
from datetime import datetime

from dotenv import load_dotenv
from AppKit import (
    NSApplication,
    NSImage,
    NSMenu,
    NSMenuItem,
    NSObject,
    NSStatusBar,
    NSVariableStatusItemLength,
)
from PyObjCTools import AppHelper

from emma import __version__
from emma.config import get_config_path
from emma.tts import say
from emma.stt import listen, request_authorization
from emma.wake_word import WakeWordDetector, WakeWordInterrupted
from emma.commands import (
    load_commands,
    load_embedding_model,
    setup_chroma_db,
    index_commands,
    find_best_command,
)
from emma.actions import run_action

CONFIRMATIONS = ["Ja?", "Hmm?", "Jaa?", "Was kann ich für dich tun?", "Japp?", "Ja, bitte?"]


def _sf_symbol(name: str) -> NSImage:
    """Load an SF Symbol by name (macOS 11+)."""
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if img is None:
        # Fallback: return an empty image so setImage_ doesn't crash
        img = NSImage.alloc().initWithSize_((18, 18))
    img.setTemplate_(True)
    return img


def get_response(command: dict, action_result: dict) -> str:
    """Determine the response text based on action result and command config."""
    responses = command.get("responses", {})
    status = action_result.get("status", "success")
    if status in responses:
        return responses[status]
    if "default" in responses:
        return responses["default"]
    return "Befehl ausgeführt."


class EmmaAppDelegate(NSObject):
    """NSApplication delegate that manages the menubar UI and emma loop."""

    def applicationDidFinishLaunching_(self, notification):
        # --- Status Bar Item ---
        self._status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        self._status_item.button().setImage_(_sf_symbol("mic.slash"))

        # --- Build Menu ---
        menu = NSMenu.alloc().init()

        self._toggle_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Start", "toggleEmma:", ""
        )
        self._toggle_item.setTarget_(self)
        self._toggle_item.setEnabled_(False)  # disabled until init complete
        menu.addItem_(self._toggle_item)

        menu.addItem_(NSMenuItem.separatorItem())

        self._login_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Start at Login", "toggleLogin:", ""
        )
        self._login_item.setTarget_(self)
        self._login_item.setEnabled_(True)
        self._update_login_checkbox()
        menu.addItem_(self._login_item)

        menu.addItem_(NSMenuItem.separatorItem())

        version_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Hey Emma v{__version__}", "", ""
        )
        version_item.setEnabled_(False)
        menu.addItem_(version_item)

        menu.addItem_(NSMenuItem.separatorItem())

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quitApp:", "q"
        )
        quit_item.setTarget_(self)
        menu.addItem_(quit_item)

        self._status_item.setMenu_(menu)

        # --- Internal state ---
        self._detector = None
        self._embed_model = None
        self._collection = None
        self._trigger_to_command = None
        self._stop_event = threading.Event()
        self._running = False
        self._loop_thread = None

        # --- Initialize on background thread ---
        t = threading.Thread(target=self._initialize, daemon=True)
        t.start()

    # ------------------------------------------------------------------ init
    def _initialize(self):
        """Load models and prepare detector (runs on background thread)."""
        warnings.simplefilter(action="ignore", category=FutureWarning)
        load_dotenv(get_config_path())
        print(f"Hey Emma v{__version__}")

        if not request_authorization():
            print("Spracherkennung nicht autorisiert.")
            AppHelper.callAfter(self._set_icon, "exclamationmark.triangle")
            return

        commands = load_commands()
        self._embed_model = load_embedding_model()
        _client, self._collection = setup_chroma_db()
        self._trigger_to_command = index_commands(
            self._collection, self._embed_model, commands
        )

        self._detector = WakeWordDetector()

        print("Initialisierung abgeschlossen.")

        # Enable toggle and auto-start
        AppHelper.callAfter(self._on_init_complete)

    def _on_init_complete(self):
        """Called on main thread after background init finishes."""
        self._toggle_item.setEnabled_(True)
        self._start_emma()

    # ------------------------------------------------------------------ start / stop
    def _start_emma(self):
        if self._running or self._detector is None:
            return
        self._running = True
        self._stop_event.clear()
        self._toggle_item.setTitle_("Stop")
        self._set_icon("mic")
        self._loop_thread = threading.Thread(target=self._emma_loop, daemon=True)
        self._loop_thread.start()

    def _stop_emma(self):
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._detector:
            self._detector.interrupt()
        self._toggle_item.setTitle_("Start")
        self._set_icon("mic.slash")

    # ------------------------------------------------------------------ loop
    def _emma_loop(self):
        """Main wake-word / STT / command loop (runs on daemon thread)."""
        detector = self._detector
        detector.start()

        say('Ok, ich bin bereit. Wenn du Hilfe benötigst, sage einfach "Hey Emma".')
        print("Lausche...")

        try:
            while not self._stop_event.is_set():
                try:
                    keyword = detector.wait_for_wake_word()
                except WakeWordInterrupted:
                    break

                if self._stop_event.is_set():
                    break

                print(f"[{datetime.now()}] Wake Word erkannt: {keyword}")
                AppHelper.callAfter(self._set_icon, "ear.fill")

                detector.stop()

                confirmation = random.choice(CONFIRMATIONS)
                say(confirmation)

                transcript = listen(timeout=5.0)

                if self._stop_event.is_set():
                    break

                if transcript:
                    cmd, distance = find_best_command(
                        self._collection,
                        self._embed_model,
                        transcript,
                        self._trigger_to_command,
                    )
                    if cmd:
                        action_result = run_action(cmd["action"])
                        response = get_response(cmd, action_result)
                        say(response)
                    else:
                        say("Ich konnte den Befehl nicht zuordnen.")
                else:
                    say("Ich konnte dich nicht verstehen. Bitte versuche es erneut.")

                if self._stop_event.is_set():
                    break

                AppHelper.callAfter(self._set_icon, "mic")
                detector.start()
        except Exception as exc:
            print(f"Emma-Loop Fehler: {exc}")
        finally:
            try:
                detector.stop()
            except Exception:
                pass
            if not self._stop_event.is_set():
                AppHelper.callAfter(self._set_icon, "mic.slash")
                AppHelper.callAfter(self._toggle_item.setTitle_, "Start")
                self._running = False

    # ------------------------------------------------------------------ UI helpers
    def _set_icon(self, symbol_name: str):
        """Update the status bar icon (must be called on main thread)."""
        self._status_item.button().setImage_(_sf_symbol(symbol_name))

    # ------------------------------------------------------------------ menu actions
    def toggleEmma_(self, sender):
        if self._running:
            self._stop_emma()
        else:
            self._start_emma()

    def toggleLogin_(self, sender):
        try:
            from ServiceManagement import SMAppService
            service = SMAppService.mainAppService()
            if service.status() == 1:  # enabled
                success, err = service.unregisterAndReturnError_(None)
                if not success:
                    print(f"Start at Login deaktivieren fehlgeschlagen: {err}")
            else:
                success, err = service.registerAndReturnError_(None)
                if not success:
                    print(f"Start at Login aktivieren fehlgeschlagen: {err}")
        except ImportError:
            print("ServiceManagement nicht verfügbar (nur im .app Bundle).")
        except Exception as exc:
            print(f"Start at Login Fehler: {exc}")
        self._update_login_checkbox()

    def _update_login_checkbox(self):
        try:
            from ServiceManagement import SMAppService
            service = SMAppService.mainAppService()
            enabled = service.status() == 1
            self._login_item.setState_(1 if enabled else 0)
        except Exception:
            self._login_item.setState_(0)

    def quitApp_(self, sender):
        self._stop_emma()
        if self._detector:
            self._detector.delete()
            self._detector = None
        NSApplication.sharedApplication().terminate_(sender)


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory
    delegate = EmmaAppDelegate.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
