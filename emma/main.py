import random
import warnings
from datetime import datetime

from dotenv import load_dotenv

from emma import __version__
from emma.config import get_config_path
from emma.tts import say
from emma.stt import listen, request_authorization
from emma.wake_word import WakeWordDetector
from emma.commands import (
    load_commands,
    load_embedding_model,
    setup_chroma_db,
    index_commands,
    find_best_command,
)
from emma.actions import run_action

CONFIRMATIONS = ["Ja?", "Hmm?", "Jaa?", "Was kann ich für dich tun?", "Japp?", "Ja, bitte?"]


def get_response(command: dict, action_result: dict) -> str:
    """Determine the response text based on action result and command config."""
    responses = command.get("responses", {})
    status = action_result.get("status", "success")

    # Try status-specific response first, then fall back to default
    if status in responses:
        return responses[status]
    if "default" in responses:
        return responses["default"]
    return "Befehl ausgeführt."


def main():
    warnings.simplefilter(action="ignore", category=FutureWarning)
    load_dotenv(get_config_path())
    print(f"Hey Emma v{__version__}")

    # Request speech recognition authorization
    if not request_authorization():
        print("Spracherkennung nicht autorisiert. Bitte in Systemeinstellungen erlauben.")
        return

    # Load commands and set up embedding search
    commands = load_commands()
    embed_model = load_embedding_model()
    client, collection = setup_chroma_db()
    trigger_to_command = index_commands(collection, embed_model, commands)

    # Initialize wake word detector
    detector = WakeWordDetector()
    detector.start()

    say('Ok, ich bin bereit. Wenn du Hilfe benötigst, sage einfach "Hey Emma".')

    print("Lausche... (Strg+C zum Beenden)")

    try:
        while True:
            keyword = detector.wait_for_wake_word()
            print(f"[{datetime.now()}] Wake Word erkannt: {keyword}")

            # Stop wake word recorder while doing STT
            detector.stop()

            # Confirm wake word
            confirmation = random.choice(CONFIRMATIONS)
            say(confirmation)

            # Listen for command via Apple Speech Recognition
            transcript = listen(timeout=5.0)

            if transcript:
                # Match against commands
                cmd, distance = find_best_command(
                    collection, embed_model, transcript, trigger_to_command
                )

                if cmd:
                    # Run action
                    action_result = run_action(cmd["action"])
                    # Get response
                    response = get_response(cmd, action_result)
                    say(response)
                else:
                    say("Ich konnte den Befehl nicht zuordnen.")
            else:
                say("Ich konnte dich nicht verstehen. Bitte versuche es erneut.")

            # Restart wake word recorder
            detector.start()

    except KeyboardInterrupt:
        print("\nBeende...")
    finally:
        detector.delete()


if __name__ == "__main__":
    main()
