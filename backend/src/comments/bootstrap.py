"""Composition root: the only place that knows which adapter backs which port.

Swapping technology (Redis -> Memcached, Elasticsearch -> Postgres FTS,
Celery -> inline) means editing this file and nothing in the core.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cache

from celery import current_app
from django.conf import settings
from django.core.cache import cache as django_cache

from comments.adapters.outbound.cache.repository import CachedCommentRepository
from comments.adapters.outbound.captcha.renderer import PillowCaptchaRenderer
from comments.adapters.outbound.captcha.store import CacheCaptchaStore, FixedAnswerCaptchaStore, RedisCaptchaStore
from comments.adapters.outbound.events.celery_publisher import BROADCAST_TASK, INDEX_TASK, CeleryEventPublisher
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

log = logging.getLogger(__name__)


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
    store: RedisCaptchaStore | CacheCaptchaStore
    if settings.REDIS_URL:
        from django_redis import get_redis_connection

        store = RedisCaptchaStore(get_redis_connection("default"))
    else:
        store = CacheCaptchaStore(django_cache)
    if settings.LOADTEST_CAPTCHA_ANSWER:
        log.warning("LOADTEST_MODE is on: captchas accept a fixed answer. Never use this in production.")
        return FixedAnswerCaptchaStore(store, settings.LOADTEST_CAPTCHA_ANSWER)
    return store


def _search_index() -> SearchIndex:
    if settings.ELASTICSEARCH_URL:
        from elasticsearch import Elasticsearch

        from comments.adapters.outbound.search.elastic import ElasticsearchSearchIndex

        writer = Elasticsearch(settings.ELASTICSEARCH_URL, request_timeout=10, retry_on_timeout=True, max_retries=2)
        reader = Elasticsearch(settings.ELASTICSEARCH_URL, request_timeout=2, max_retries=0)
        return ElasticsearchSearchIndex(writer, settings.ELASTICSEARCH_INDEX, search_client=reader)
    return DatabaseSearchIndex()


def _send_comment_posted(payload: dict[str, object]) -> None:
    if settings.CELERY_TASK_ALWAYS_EAGER:  # no broker configured: handle inline
        _handle_inline(CommentPosted(**payload))  # type: ignore[arg-type]
        return
    # Sent by name: the tasks live in an inbound adapter, which the composition
    # root must not import (see .importlinter). Two tasks, so retrying the
    # indexing never re-broadcasts the comment.
    current_app.send_task(BROADCAST_TASK, args=[payload])
    current_app.send_task(INDEX_TASK, args=[payload])


def _handle_inline(event: CommentPosted) -> None:
    container().handle_comment_posted(event)


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
            events=CeleryEventPublisher(transactions, _send_comment_posted, _handle_inline),
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
