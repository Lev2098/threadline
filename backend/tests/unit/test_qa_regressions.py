"""Regression tests for findings of the QA pass (one test per confirmed bug)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from comments.adapters.outbound.events.celery_publisher import CeleryEventPublisher
from comments.application.use_cases import GetThread, HandleCommentPosted, SearchComments
from comments.domain.comment import MAX_DEPTH, child_path, is_valid_path
from comments.domain.errors import CaptchaError, MarkupError, NotFoundError, ValidationError
from comments.domain.events import CommentPosted
from comments.domain.markup import CommentText
from comments.domain.values import Email, HomePage, UserName, restore
from tests.fakes import FakeTransactions, InMemorySearchIndex, RecordingBroadcaster
from tests.unit.test_use_cases import World


@pytest.fixture
def world() -> World:
    return World()


# --- captcha ------------------------------------------------------------------


def test_non_ascii_captcha_answer_is_a_mismatch_not_a_crash(world: World) -> None:
    with pytest.raises(CaptchaError):
        world.post(world.command(captcha_answer="абвгде"))


def test_missing_parent_does_not_burn_the_captcha(world: World) -> None:
    cmd = world.command(parent_id=999)
    with pytest.raises(NotFoundError):
        world.post(cmd)
    assert cmd.captcha_key in world.captchas.data  # still usable for the retry


# --- thread depth and cursors ----------------------------------------------------


def test_thread_depth_is_capped(world: World) -> None:
    parent = world.post(world.command())
    for _ in range(MAX_DEPTH):
        parent = world.post(world.command(parent_id=parent.id))
    assert parent.depth == MAX_DEPTH
    with pytest.raises(ValidationError) as exc:
        world.post(world.command(parent_id=parent.id))
    assert exc.value.field == "parent_id"


@pytest.mark.parametrize("cursor", ["0", "00", "abc", "0000000001.", "0000000001..0000000002", "1" * 10 + ".1"])
def test_malformed_cursor_is_rejected(world: World, cursor: str) -> None:
    root = world.post(world.command())
    with pytest.raises(ValidationError):
        GetThread(world.repo)(root.id, cursor)  # type: ignore[arg-type]


def test_valid_path_shape() -> None:
    assert is_valid_path(child_path(child_path("", 1), 2))
    assert not is_valid_path("")


def test_path_overflow_is_refused() -> None:
    with pytest.raises(OverflowError):
        child_path("", 10**10)


def test_search_page_is_clamped(world: World) -> None:
    index = InMemorySearchIndex()
    page = SearchComments(index, world.repo)("x", page=10**9)
    assert page.page == 400


# --- markup -------------------------------------------------------------------------


@pytest.mark.parametrize("source", ["\u200b", "\u200b\u200c\ufeff", " \u2060 "])
def test_invisible_only_text_is_empty(source: str) -> None:
    with pytest.raises(MarkupError):
        CommentText.parse(source)


def test_xml_illegal_characters_are_removed() -> None:
    html = CommentText.parse("a\x01b\x0bc\ufffe").html
    assert html == "abc"


def test_legacy_entities_without_semicolon_stay_literal() -> None:
    html = CommentText.parse("http://shop.ua/?id=1&copy=2&not=3 &amp; &#169;").html
    assert html == "http://shop.ua/?id=1&amp;copy=2&amp;not=3 &amp; ©"


def test_crlf_text_of_exactly_max_length_is_accepted() -> None:
    assert len(CommentText.parse("a" * 4998 + "\r\ny").source) == 5000


# --- values ---------------------------------------------------------------------------


@pytest.mark.parametrize("email", ["a..b@example.com", ".a@example.com", "a.@example.com"])
def test_malformed_local_parts_are_rejected(email: str) -> None:
    with pytest.raises(ValidationError):
        Email(email)


@pytest.mark.parametrize(
    "url",
    [
        "https://пример.укр/",
        "https://xn--e1afmkfd.xn--p1ai",
        "http://127.0.0.1:8000/x",
        "http://[::1]/",
        "http://localhost/",
    ],
)
def test_idn_ip_and_localhost_home_pages_are_accepted(url: str) -> None:
    assert HomePage(url).value == url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com:99999/",
        "https://example.com:0/",
        "https://u:p@example.com/",
        "https://exa mple.com",
        "https://1.2",
    ],
)
def test_bad_home_pages_are_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        HomePage(url)


def test_restore_skips_validation_for_stored_rows() -> None:
    assert restore(UserName, "Legacy Name").value == "Legacy Name"


# --- events -----------------------------------------------------------------------------


def test_broadcast_and_index_run_independently(world: World) -> None:
    world.post(world.command())
    index, broadcaster = InMemorySearchIndex(), RecordingBroadcaster()
    handler = HandleCommentPosted(world.repo, index, broadcaster)
    event = world.events.events[0]

    handler.index(event)
    handler.index(event)  # a retried index never re-broadcasts
    assert broadcaster.sent == [] and list(index.docs) == [1]


def test_broker_outage_falls_back_to_inline_handling() -> None:
    handled: list[CommentPosted] = []

    def broken_send(payload: dict[str, object]) -> None:
        raise ConnectionRefusedError("broker down")

    tx = FakeTransactions()
    publisher = CeleryEventPublisher(tx, broken_send, handled.append)
    event = CommentPosted(comment_id=1, root_id=1, parent_id=None)
    with tx.atomic():
        publisher.publish(event)
    assert handled == [event]


def test_fallback_failure_is_swallowed() -> None:
    def boom(*_: object) -> None:
        raise RuntimeError

    tx = FakeTransactions()
    with tx.atomic():
        CeleryEventPublisher(tx, boom, boom).publish(replace(CommentPosted(1, 1, None)))
