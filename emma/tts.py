import subprocess


def say(text: str, voice: str = "Petra (Premium)", rate: int = 210) -> None:
    """Speak text using macOS say command."""
    result = subprocess.run(
        ["say", "-v", voice, "-r", str(rate), text],
        capture_output=True,
    )
    if result.returncode != 0:
        # Fallback to default voice
        subprocess.run(["say", "-r", str(rate), text])
