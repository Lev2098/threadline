from __future__ import annotations

from dataclasses import replace

import pytest

from comments.application.dto import ListRootsQuery, PostCommentCommand
from comments.application.use_cases import (
    GetThread,
    HandleCommentPosted,
    IssueCaptcha,
    ListRootComments,
    PostComment,
    PreviewComment,
    SearchComments,
)
from comments.domain.attachment import Upload
from comments.domain.errors import CaptchaError, InvalidInput, NotFoundError
from comments.domain.values import ClientFingerprint, Ordering
from tests.fakes import (
    DictCaptchaStore,
    DictStorage,
    FakeTransactions,
    IdentitySanitizer,
    InMemoryCommentRepository,
    InMemorySearchIndex,
    RecordingBroadcaster,
    RecordingPublisher,
    StubCaptchaRenderer,
    StubImageProcessor,
)

FINGERPRINT = ClientFingerprint(client_id="c1", ip="127.0.0.1", user_agent="pytest")


class World:
    def __init__(self) -> None:
        self.repo = InMemoryCommentRepository()
        self.events = RecordingPublisher()
        self.captchas = DictCaptchaStore()
        self.images = StubImageProcessor()
        self.storage = DictStorage()
        self.post = PostComment(
            repository=self.repo,
            transactions=FakeTransactions(),
            events=self.events,
            captchas=self.captchas,
            images=self.images,
            storage=self.storage,
            sanitizer=IdentitySanitizer(),
        )
        self.issue_captcha = IssueCaptcha(self.captchas, StubCaptchaRenderer())

    def command(self, **overrides: object) -> PostCommentCommand:
        captcha = self.issue_captcha()
        answer = self.captchas.data[captcha.key]
        cmd = PostCommentCommand(
            username="Anonym",
            email="anon@example.com",
            text="Hello <strong>world</strong>",
            captcha_key=captcha.key,
            captcha_answer=answer.lower(),
            fingerprint=FINGERPRINT,
        )
        return replace(cmd, **overrides)  # type: ignore[arg-type]


@pytest.fixture
def world() -> World:
    return World()


def test_post_root_comment_publishes_event(world: World) -> None:
    comment = world.post(world.command())
    assert comment.id == 1 and comment.root_id == 1 and comment.is_root
    assert comment.text.html == "Hello <strong>world</strong>"
    assert [e.comment_id for e in world.events.events] == [1]


def test_reply_inherits_root_and_bumps_counter(world: World) -> None:
    root = world.post(world.command())
    reply = world.post(world.command(parent_id=root.id))
    nested = world.post(world.command(parent_id=reply.id))
    assert nested.root_id == root.id and nested.depth == 2
    assert world.repo.get(root.id).replies_count == 2  # type: ignore[arg-type,union-attr]


def test_all_field_errors_are_reported_together(world: World) -> None:
    with pytest.raises(InvalidInput) as exc:
        world.post(world.command(username="bad name", email="nope", text="<script>", captcha_answer=""))
    assert set(exc.value.errors) == {"username", "email", "text", "captcha"}


def test_captcha_is_single_use(world: World) -> None:
    cmd = world.command()
    world.post(cmd)
    with pytest.raises(CaptchaError):
        world.post(cmd)


def test_wrong_captcha_rejected(world: World) -> None:
    with pytest.raises(CaptchaError):
        world.post(world.command(captcha_answer="zzzzzz"))
    assert world.repo.rows == {}


def test_reply_to_missing_parent(world: World) -> None:
    with pytest.raises(NotFoundError):
        world.post(world.command(parent_id=999))


def test_image_is_resized_and_stored(world: World) -> None:
    comment = world.post(world.command(upload=Upload("cat.png", b"\x89PNG\r\n\x1a\nDATA")))
    assert world.images.calls == [(320, 240)]
    assert comment.attachment is not None and comment.attachment.width == 320
    assert comment.attachment.path in world.storage.files


def test_text_file_stored_as_is(world: World) -> None:
    comment = world.post(world.command(upload=Upload("notes.txt", b"hello")))
    assert comment.attachment is not None and comment.attachment.kind == "text"
    assert world.images.calls == []


def test_list_roots_default_lifo_and_clamps_page(world: World) -> None:
    for name in ["Bob", "alice", "Carl"]:
        world.post(world.command(username=name))
    listing = ListRootComments(world.repo)

    page = listing(ListRootsQuery(page=99))
    assert page.page == 1 and page.total == 3
    assert [c.author.username.value for c in page.items] == ["Carl", "alice", "Bob"]

    by_name = listing(ListRootsQuery(ordering=Ordering.parse("username")))
    assert [c.author.username.value for c in by_name.items] == ["alice", "Bob", "Carl"]


def test_thread_keyset_pagination(world: World) -> None:
    root = world.post(world.command())
    for _ in range(5):
        world.post(world.command(parent_id=root.id))
    get_thread = GetThread(world.repo)

    first = get_thread(root.id, limit=3)  # type: ignore[arg-type]
    assert len(first.items) == 3 and first.next_cursor
    second = get_thread(root.id, cursor=first.next_cursor, limit=3)  # type: ignore[arg-type]
    assert len(second.items) == 2 and second.next_cursor is None


def test_thread_of_reply_is_not_found(world: World) -> None:
    root = world.post(world.command())
    reply = world.post(world.command(parent_id=root.id))
    with pytest.raises(NotFoundError):
        GetThread(world.repo)(reply.id)  # type: ignore[arg-type]


def test_preview_returns_sanitized_html() -> None:
    assert PreviewComment(IdentitySanitizer())("<i>x</i> < y") == "<i>x</i> &lt; y"


def test_handle_event_indexes_and_broadcasts(world: World) -> None:
    index, broadcaster = InMemorySearchIndex(), RecordingBroadcaster()
    world.post(world.command(text="Elasticsearch is <i>fast</i>"))
    HandleCommentPosted(world.repo, index, broadcaster)(world.events.events[0])

    assert [c.id for c in broadcaster.sent] == [1]
    page = SearchComments(index, world.repo)("FAST")
    assert page.total == 1 and page.items[0].id == 1
