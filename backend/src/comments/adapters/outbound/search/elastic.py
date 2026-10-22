from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from elasticsearch import Elasticsearch, NotFoundError, helpers

from comments.domain.comment import Comment

log = logging.getLogger(__name__)

INDEX_SETTINGS: dict[str, Any] = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "analyzer": {
            # Comments are mixed Ukrainian / Russian / English: ICU-free
            # setup that lowercases and folds accents works for all three.
            "comment_text": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "asciifolding"],
            }
        }
    },
}
INDEX_MAPPINGS: dict[str, Any] = {
    "properties": {
        "text": {"type": "text", "analyzer": "comment_text"},
        "username": {"type": "text", "analyzer": "comment_text", "fields": {"raw": {"type": "keyword"}}},
        "email": {"type": "keyword"},
        "root_id": {"type": "long"},
        "created_at": {"type": "date"},
    }
}


def _document(comment: Comment) -> dict[str, Any]:
    return {
        "text": comment.text.plain,
        "username": comment.author.username.value,
        "email": comment.author.email.value,
        "root_id": comment.root_id,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


class ElasticsearchSearchIndex:
    def __init__(self, client: Elasticsearch, index: str) -> None:
        self._client = client
        self._index = index

    def ensure_index(self) -> bool:
        if self._client.indices.exists(index=self._index):
            return False
        self._client.indices.create(index=self._index, settings=INDEX_SETTINGS, mappings=INDEX_MAPPINGS)
        return True

    def index(self, comment: Comment) -> None:
        self._client.index(index=self._index, id=str(comment.id), document=_document(comment))

    def bulk_index(self, comments: Iterable[Comment]) -> int:
        actions = ({"_index": self._index, "_id": str(c.id), "_source": _document(c)} for c in comments)
        ok, _ = helpers.bulk(self._client, actions, chunk_size=2000, request_timeout=120)
        return ok

    def search(self, query: str, offset: int, limit: int) -> tuple[list[int], int]:
        try:
            response = self._client.search(
                index=self._index,
                query={
                    "multi_match": {
                        "query": query,
                        "fields": ["text", "username^2"],
                        "fuzziness": "AUTO",
                        "operator": "and",
                    }
                },
                sort=["_score", {"created_at": "desc"}],
                from_=offset,
                size=limit,
                source=False,
                track_total_hits=10_000,
            )
        except NotFoundError:
            log.warning("Search index %s is missing; run `manage.py search_reindex`", self._index)
            return [], 0
        hits = response["hits"]
        return [int(hit["_id"]) for hit in hits["hits"]], int(hits["total"]["value"])
