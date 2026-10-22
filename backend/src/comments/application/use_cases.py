"""Use cases: one class per user intention, dependencies injected via ports.

Use cases know nothing about HTTP, ORM, Redis or Celery; the same instances
serve REST, GraphQL, WebSocket and background workers.
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Callable

from comments.application.dto import (
    Captcha,
    ListRootsQuery,
    Page,
    PostCommentCommand,
    ThreadSlice,
)
from comments.application.ports import (
    Broadcaster,
    CaptchaRenderer,
    CaptchaStore,
    CommentRepository,
    EventPublisher,
    FileStorage,
    HtmlSanitizer,
    ImageProcessor,
    SearchIndex,
    TransactionManager,
)
from comments.domain.attachment import (
    IMAGE_MAX_HEIGHT,
    IMAGE_MAX_WIDTH,
    Attachment,
    AttachmentKind,
    Upload,
)
from comments.domain.comment import Comment
from comments.domain.errors import CaptchaError, DomainError, InvalidInput, NotFoundError
from comments.domain.events import CommentPosted
from comments.domain.markup import CommentText
from comments.domain.values import Author, Email, HomePage, UserName

CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"  # no 0/O, 1/l/I
CAPTCHA_LENGTH = 6
CAPTCHA_TTL_SECONDS = 300
THREAD_PAGE_MAX = 500
SEARCH_PAGE_SIZE = 25


class IssueCaptcha:
    def __init__(self, store: CaptchaStore, renderer: CaptchaRenderer) -> None:
        self._store = store
        self._renderer = renderer

    def __call__(self) -> Captcha:
        answer = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(CAPTCHA_LENGTH))
        key = uuid.uuid4().hex
        self._store.save(key, answer, CAPTCHA_TTL_SECONDS)
        return Captcha(key=key, image_png=self._renderer.render(answer), ttl_seconds=CAPTCHA_TTL_SECONDS)


class PreviewComment:
    def __init__(self, sanitizer: HtmlSanitizer) -> None:
        self._sanitizer = sanitizer

    def __call__(self, text: str) -> str:
        return self._sanitizer.clean(CommentText.parse(text).html)


class PostComment:
    def __init__(
        self,
        *,
        repository: CommentRepository,
        transactions: TransactionManager,
        events: EventPublisher,
        captchas: CaptchaStore,
        images: ImageProcessor,
        storage: FileStorage,
        sanitizer: HtmlSanitizer,
    ) -> None:
        self._repository = repository
        self._transactions = transactions
        self._events = events
        self._captchas = captchas
        self._images = images
        self._storage = storage
        self._sanitizer = sanitizer

    def __call__(self, cmd: PostCommentCommand) -> Comment:
        # Cheap checks first, captcha (single-use) next, file processing last.
        author, text, kind = self._validate(cmd)
        self._check_captcha(cmd.captcha_key, cmd.captcha_answer)
        if cmd.parent_id is not None and self._repository.get(cmd.parent_id) is None:
            raise NotFoundError("The comment you are replying to does not exist.", field="parent_id")

        attachment = self._store_attachment(cmd.upload, kind) if cmd.upload and kind else None
        comment = Comment(
            author=author,
            text=CommentText(source=text.source, html=self._sanitizer.clean(text.html)),
            fingerprint=cmd.fingerprint,
            parent_id=cmd.parent_id,
            attachment=attachment,
        )
        with self._transactions.atomic():
            saved = self._repository.add(comment)
            assert saved.id is not None and saved.root_id is not None
            self._events.publish(CommentPosted(comment_id=saved.id, root_id=saved.root_id, parent_id=saved.parent_id))
        return saved

    def _validate(self, cmd: PostCommentCommand) -> tuple[Author, CommentText, AttachmentKind | None]:
        errors: dict[str, str] = {}

        def attempt[T](build: Callable[[], T]) -> T | None:
            try:
                return build()
            except DomainError as exc:
                errors[exc.field or "non_field"] = exc.message
                return None

        username = attempt(lambda: UserName(cmd.username.strip()))
        email = attempt(lambda: Email.normalized(cmd.email))
        home_page = attempt(lambda: HomePage.optional(cmd.home_page))
        text = attempt(lambda: CommentText.parse(cmd.text))
        upload = cmd.upload
        kind = attempt(upload.detect_kind) if upload else None
        if not cmd.captcha_answer.strip():
            errors["captcha"] = "Enter the characters from the image."

        if errors:
            raise InvalidInput(errors)
        assert username and email and text
        return Author(username, email, home_page), text, kind

    def _check_captcha(self, key: str, answer: str) -> None:
        expected = self._captchas.pop(key) if key else None
        # Case-insensitive on purpose: distortion makes case hard to read.
        if expected is None or not secrets.compare_digest(expected.lower(), answer.strip().lower()):
            raise CaptchaError("The characters from the image do not match. Try a new image.", field="captcha")

    def _store_attachment(self, upload: Upload, kind: AttachmentKind) -> Attachment:
        stem = uuid.uuid4().hex
        if kind is AttachmentKind.TEXT:
            path = self._storage.save(f"{stem}.txt", upload.content)
            return Attachment(kind, path, upload.filename[:255], len(upload.content))

        image = self._images.fit(upload.content, IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT)
        ext = "jpg" if image.format.value == "jpeg" else image.format.value
        path = self._storage.save(f"{stem}.{ext}", image.content)
        return Attachment(kind, path, upload.filename[:255], len(image.content), image.width, image.height)


class ListRootComments:
    def __init__(self, repository: CommentRepository) -> None:
        self._repository = repository

    def __call__(self, query: ListRootsQuery) -> Page[Comment]:
        total = self._repository.count_roots()
        last_page = max(1, -(-total // query.page_size))
        page = min(max(1, query.page), last_page)
        items = self._repository.list_roots(query.ordering, (page - 1) * query.page_size, query.page_size)
        return Page(items=items, page=page, page_size=query.page_size, total=total)


class GetThread:
    def __init__(self, repository: CommentRepository) -> None:
        self._repository = repository

    def __call__(self, root_id: int, cursor: str | None = None, limit: int = THREAD_PAGE_MAX) -> ThreadSlice[Comment]:
        root = self._repository.get(root_id)
        if root is None or not root.is_root:
            raise NotFoundError("Thread not found.")
        limit = min(max(1, limit), THREAD_PAGE_MAX)
        # Fetch one extra row to know whether another slice exists.
        rows = self._repository.thread(root_id, cursor, limit + 1)
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ThreadSlice(items=rows, next_cursor=rows[-1].path if has_more and rows else None)


class SearchComments:
    def __init__(self, index: SearchIndex, repository: CommentRepository) -> None:
        self._index = index
        self._repository = repository

    def __call__(self, query: str, page: int = 1) -> Page[Comment]:
        query = query.strip()[:200]
        if not query:
            return Page(items=[], page=1, page_size=SEARCH_PAGE_SIZE, total=0)
        page = max(1, page)
        ids, total = self._index.search(query, (page - 1) * SEARCH_PAGE_SIZE, SEARCH_PAGE_SIZE)
        return Page(items=self._repository.get_many(ids), page=page, page_size=SEARCH_PAGE_SIZE, total=total)


class HandleCommentPosted:
    """Async side effects of a new comment: search indexing and live push."""

    def __init__(self, repository: CommentRepository, index: SearchIndex, broadcaster: Broadcaster) -> None:
        self._repository = repository
        self._index = index
        self._broadcaster = broadcaster

    def __call__(self, event: CommentPosted) -> None:
        comment = self._repository.get(event.comment_id)
        if comment is None:  # deleted between commit and handling
            return
        self._broadcaster.comment_posted(comment)
        self._index.index(comment)
