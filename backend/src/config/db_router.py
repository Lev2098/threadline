from __future__ import annotations

from typing import Any

from django.db import connections


class PrimaryReplicaRouter:
    """Reads go to the replica, writes to the primary.

    Enabled only when POSTGRES_REPLICA_HOST is set. Inside an open transaction
    on the primary, reads stay on the primary too, so a use case never misses
    a row it has just written because of replication lag.
    """

    def db_for_read(self, model: type, **hints: Any) -> str:
        return "default" if connections["default"].in_atomic_block else "replica"

    def db_for_write(self, model: type, **hints: Any) -> str:
        return "default"

    def allow_relation(self, obj1: Any, obj2: Any, **hints: Any) -> bool:
        return True

    def allow_migrate(self, db: str, app_label: str, **hints: Any) -> bool:
        return db == "default"
