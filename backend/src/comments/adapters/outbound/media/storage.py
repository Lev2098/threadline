from __future__ import annotations

from datetime import UTC, datetime

from django.core.files.base import ContentFile
from django.core.files.storage import Storage, default_storage


class DjangoFileStorage:
    """Delegates to Django's storage API, so switching to S3 is a settings
    change (``STORAGES``), not a code change."""

    def __init__(self, storage: Storage | None = None) -> None:
        self._storage = storage or default_storage

    def save(self, name: str, content: bytes) -> str:
        folder = datetime.now(UTC).strftime("attachments/%Y/%m")
        return self._storage.save(f"{folder}/{name}", ContentFile(content))

    def url(self, path: str) -> str:
        return self._storage.url(path)
