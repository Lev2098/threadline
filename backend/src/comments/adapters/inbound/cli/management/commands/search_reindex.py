from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from comments.adapters.outbound.search.elastic import ElasticsearchSearchIndex
from comments.bootstrap import container


class Command(BaseCommand):
    help = "Create the Elasticsearch index if missing and optionally (re)index all comments."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--ensure-only", action="store_true", help="Only create the index, don't fill it.")

    def handle(self, *args: Any, **opts: Any) -> None:
        index = container().search_index
        if not isinstance(index, ElasticsearchSearchIndex):
            self.stdout.write("ELASTICSEARCH_URL is not set: database search is used, nothing to index.")
            return
        created = index.ensure_index()
        self.stdout.write(f"Index {'created' if created else 'already exists'}.")
        if opts["ensure_only"]:
            return
        count = index.bulk_index(container().db_repository.iterate_all())
        self.stdout.write(self.style.SUCCESS(f"Indexed {count:,} comments."))
