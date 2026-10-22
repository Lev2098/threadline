"""Composition root: the only place that knows which adapter backs which port.

Swapping technology (Redis -> Memcached, Elasticsearch -> Postgres FTS,
Celery -> inline) means editing this file and nothing in the core.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from celery import current_app
from django.conf import settings
from django.core.cache import cache as django_cache

from comments.adapters.outbound.cache.repository import CachedCommentRepository
from comments.adapters.outbound.captcha.renderer import PillowCaptchaRenderer
from comments.adapters.outbound.captcha.store import CacheCaptchaStore, RedisCaptchaStore
from comments.adapters.outbound.events.celery_publisher import COMMENT_POSTED_TASK, CeleryEventPublisher
from comments.adapters.outbound.media.images import PillowImageProcessor
from comments.adapters.outbound.media.storage import DjangoFileStorage
from comments.adapters.outbound.persistence.repository import DjangoCommentRepository, DjangoTransactions
from comments.adapters.outbound.realtime.broadcaster import ChannelsBroadcaster
from comments.adapters.outbound.sanitizer import Nh3Sanitizer
from comments.adapters.outbound.search.database import DatabaseSearchIndex
from comments.application.ports import CaptchaStore, SearchIndex
from comments.application.use_cases import (
    GetThread,
    HandleCommentPosted,
    IssueCaptcha,
    ListRootComments,
    PostComment,
    PreviewComment,
    SearchComments,
)
from comments.domain.events import CommentPosted


@dataclass(frozen=True)
class Container:
    issue_captcha: IssueCaptcha
    preview_comment: PreviewComment
    post_comment: PostComment
    list_root_comments: ListRootComments
    get_thread: GetThread
    search_comments: SearchComments
    handle_comment_posted: HandleCommentPosted
    search_index: SearchIndex
    db_repository: DjangoCommentRepository


def _captcha_store() -> CaptchaStore:
    if settings.REDIS_URL:
        from django_redis import get_redis_connection

        return RedisCaptchaStore(get_redis_connection("default"))
    return CacheCaptchaStore(django_cache)


def _search_index() -> SearchIndex:
    if settings.ELASTICSEARCH_URL:
        from elasticsearch import Elasticsearch

        from comments.adapters.outbound.search.elastic import ElasticsearchSearchIndex

        client = Elasticsearch(settings.ELASTICSEARCH_URL, request_timeout=5, retry_on_timeout=True, max_retries=2)
        return ElasticsearchSearchIndex(client, settings.ELASTICSEARCH_INDEX)
    return DatabaseSearchIndex()


def _send_comment_posted(payload: dict[str, object]) -> None:
    if settings.CELERY_TASK_ALWAYS_EAGER:  # no broker configured: handle inline
        container().handle_comment_posted(CommentPosted(**payload))  # type: ignore[arg-type]
        return
    # Sent by name: the task lives in an inbound adapter, which the composition
    # root must not import (see .importlinter).
    current_app.send_task(COMMENT_POSTED_TASK, args=[payload])


@cache
def container() -> Container:
    transactions = DjangoTransactions()
    db_repository = DjangoCommentRepository()
    repository = CachedCommentRepository(db_repository, django_cache, transactions)
    sanitizer = Nh3Sanitizer()
    search_index = _search_index()

    return Container(
        issue_captcha=IssueCaptcha(_captcha_store(), PillowCaptchaRenderer()),
        preview_comment=PreviewComment(sanitizer),
        post_comment=PostComment(
            repository=repository,
            transactions=transactions,
            events=CeleryEventPublisher(transactions, _send_comment_posted),
            captchas=_captcha_store(),
            images=PillowImageProcessor(),
            storage=DjangoFileStorage(),
            sanitizer=sanitizer,
        ),
        list_root_comments=ListRootComments(repository),
        get_thread=GetThread(repository),
        search_comments=SearchComments(search_index, repository),
        # Workers bypass the cache and read the primary: the event arrives right
        # after commit, when a replica may not have the row yet.
        handle_comment_posted=HandleCommentPosted(
            DjangoCommentRepository(using="default"), search_index, ChannelsBroadcaster()
        ),
        search_index=search_index,
        db_repository=db_repository,
    )
