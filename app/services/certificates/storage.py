"""Local-filesystem storage for uploaded certificate templates/signatures.

A single-node MVP (see Settings.certificate_storage_path) — swap for
object storage if the deployment grows beyond one server.
"""
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


def storage_root() -> Path:
    root = Path(settings.certificate_storage_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_bytes(content: bytes, *, suffix: str) -> str:
    """Save `content` under a random filename; returns the path relative to
    storage_root() (what gets persisted in the DB), never a caller-supplied name
    (avoids path traversal from uploaded filenames)."""
    filename = f"{uuid4()}{suffix}"
    (storage_root() / filename).write_bytes(content)
    return filename


def resolve(relative_path: str) -> Path:
    return storage_root() / relative_path
