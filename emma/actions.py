import socket
import shutil
from typing import Callable

import psutil


def check_internet() -> dict:
    """Check internet connectivity by connecting to Google DNS."""
    try:
        socket.setdefaulttimeout(3)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("8.8.8.8", 53))
        s.close()
        return {"status": "success"}
    except OSError:
        return {"status": "failure"}


def check_status() -> dict:
    """Check overall system status: internet, disk, memory."""
    internet = check_internet()
    if internet["status"] == "failure":
        return {"status": "failure", "data": {"reason": "no_internet"}}

    disk = shutil.disk_usage("/")
    disk_free_gb = disk.free / (1024 ** 3)
    if disk_free_gb < 1.0:
        return {"status": "failure", "data": {"reason": "low_disk"}}

    mem = psutil.virtual_memory()
    if mem.percent > 90:
        return {"status": "failure", "data": {"reason": "low_memory"}}

    return {"status": "success"}


def check_docker() -> dict:
    """Check if Docker daemon is reachable."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return {"status": "success"}
    except Exception:
        return {"status": "failure"}


def action_none() -> dict:
    """No-op action, always succeeds."""
    return {"status": "success"}


ACTION_REGISTRY: dict[str, Callable] = {
    "check_internet": check_internet,
    "check_status": check_status,
    "check_docker": check_docker,
    "none": action_none,
}


def run_action(action_name: str) -> dict:
    """Run an action by name from the registry."""
    action_fn = ACTION_REGISTRY.get(action_name)
    if action_fn is None:
        return {"status": "success"}
    return action_fn()
