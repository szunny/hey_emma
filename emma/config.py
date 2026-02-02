"""Resource and configuration path helpers for Hey Emma.

Handles the difference between running from source (development)
and running inside a PyInstaller .app bundle.
"""

import sys
from pathlib import Path


def is_frozen() -> bool:
    """Return True if running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def get_resource_dir() -> Path:
    """Return the directory containing bundled resources.

    Frozen (PyInstaller):  sys._MEIPASS / resources
    Development:           project root (next to emma/ package)
    """
    if is_frozen():
        return Path(sys._MEIPASS) / "resources"
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    """Return writable user data directory.

    ~/Library/Application Support/HeyEmma/
    Created on first access.
    """
    data_dir = Path.home() / "Library" / "Application Support" / "HeyEmma"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_config_path() -> Path:
    """Return path to the .env configuration file.

    Frozen:      ~/Library/Application Support/HeyEmma/.env
    Development: .env in the project root (fallback)
    """
    if is_frozen():
        return get_data_dir() / ".env"
    # In development, try user data dir first, then project root
    user_env = get_data_dir() / ".env"
    if user_env.exists():
        return user_env
    return get_resource_dir() / ".env"
