"""Generate realistic data volume, e.g. the 1,000,000 comments from the brief.

Rows are written with ``bulk_create`` and pre-assigned ids, so materialized
paths can be computed in Python without an UPDATE per row. ~1M rows take a
couple of minutes on a laptop.
"""

from __future__ import annotations

import random
import time
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandParser
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from comments.adapters.inbound.cli import demo_text
from comments.adapters.outbound.persistence.models import CommentRecord
from comments.domain.comment import child_path


class Command(BaseCommand):
    help = "Seed the database with N generated comments (default 10 000)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--count", type=int, default=10_000)
        parser.add_argument("--root-ratio", type=float, default=0.3, help="Share of root comments (0..1).")
        parser.add_argument("--batch", type=int, default=5_000)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--span-days", type=float, default=365, help="Spread timestamps over this many days.")
        parser.add_argument(
            "--until-days-ago", type=float, default=0, help="Newest generated comment is this many days old."
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        rng = random.Random(opts["seed"])  # noqa: S311 - test data, not crypto
        total, batch = opts["count"], opts["batch"]
        root_ratio = opts["root_ratio"]
        next_id = self._reserve_ids(total)
        end_time = timezone.now() - timedelta(days=opts["until_days_ago"])
        start_time = end_time - timedelta(days=opts["span_days"])
        step = (end_time - start_time) / max(total, 1)
        created = 0
        started = time.monotonic()

        while created < total:
            size = min(batch, total - created)
            rows: list[CommentRecord] = []
            roots: list[CommentRecord] = []
            thread_members: dict[int, list[CommentRecord]] = {}

            for i in range(size):
                ts = start_time + step * (created + i)
                # Roots and replies interleave over time, like real traffic.
                if not roots or rng.random() < root_ratio:
                    record = self._row(rng, next_id, None, ts)
                    record.root_id, record.path = next_id, child_path("", next_id)
                    roots.append(record)
                    thread_members[next_id] = [record]
                else:
                    root = rng.choice(roots)
                    parent = rng.choice(thread_members[root.id][-8:])  # replies cluster near recent ones
                    record = self._row(rng, next_id, parent.id, ts)
                    record.root_id, record.path = root.id, child_path(parent.path, next_id)
                    root.replies_count += 1
                    thread_members[root.id].append(record)
                rows.append(record)
                next_id += 1

            with transaction.atomic():
                CommentRecord.objects.bulk_create(rows, batch_size=batch)
            created += size
            rate = created / max(time.monotonic() - started, 1e-6)
            self.stdout.write(f"  {created:>9,} / {total:,}  ({rate:,.0f} rows/s)")

        # Invalidate cached root pages/count without FLUSHDB: the same Redis
        # holds live WebSocket groups, pending captchas and throttle counters.
        cache.delete_many(["roots:ver", "roots:count"])
        self.stdout.write(self.style.SUCCESS(f"Seeded {created:,} comments."))

    @staticmethod
    def _row(rng: random.Random, pk: int, parent_id: int | None, ts: Any) -> CommentRecord:
        name = demo_text.username(rng)
        # Generated phrases contain only allowed, balanced tags, so source == html.
        text = demo_text.root_text(rng) if parent_id is None else demo_text.reply_text(rng)
        return CommentRecord(
            id=pk,
            parent_id=parent_id,
            username=name,
            email=demo_text.email(rng, name),
            text_source=text,
            text_html=text,
            client_id="seed",
            ip="127.0.0.1",
            user_agent="seed_comments",
            created_at=ts,
        )

    @staticmethod
    def _reserve_ids(count: int) -> int:
        """Move the id sequence past the block we insert, *before* inserting,
        so live traffic during seeding can't collide with our explicit ids."""
        if connection.vendor != "postgresql":
            return (CommentRecord.objects.aggregate(m=Max("id"))["m"] or 0) + 1
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence('comments', 'id'),"
                " GREATEST(nextval(pg_get_serial_sequence('comments', 'id')),"
                " (SELECT COALESCE(MAX(id), 0) + 1 FROM comments)) + %s) - %s",
                [count, count],
            )
            return int(cursor.fetchone()[0])
