import pytest

from comments.domain.attachment import AttachmentKind, Upload
from comments.domain.comment import child_path
from comments.domain.errors import AttachmentError, ValidationError
from comments.domain.values import Email, HomePage, Ordering, SortDirection, SortField, UserName


@pytest.mark.parametrize("value", ["Anonym", "Rum8", "a", "ABC123"])
def test_username_accepts_latin_and_digits(value: str) -> None:
    assert UserName(value).value == value


@pytest.mark.parametrize("value", ["", "with space", "Кирилиця", "under_score", "x" * 65, "<b>"])
def test_username_rejects_others(value: str) -> None:
    with pytest.raises(ValidationError):
        UserName(value)


def test_email_normalizes_domain_case() -> None:
    assert Email.normalized("  John@Example.COM ").value == "John@example.com"


@pytest.mark.parametrize("value", ["", "no-at", "a@b", "a@@b.com", "a b@c.com"])
def test_email_rejects_invalid(value: str) -> None:
    with pytest.raises(ValidationError):
        Email(value)


def test_home_page_optional() -> None:
    assert HomePage.optional("") is None
    assert HomePage.optional("https://dzencode.com/path?q=1") is not None
    with pytest.raises(ValidationError):
        HomePage.optional("javascript:alert(1)")


@pytest.mark.parametrize(
    ("raw", "field", "direction"),
    [
        (None, SortField.CREATED_AT, SortDirection.DESC),
        ("-created_at", SortField.CREATED_AT, SortDirection.DESC),
        ("created_at", SortField.CREATED_AT, SortDirection.ASC),
        ("username", SortField.USERNAME, SortDirection.ASC),
        ("-email", SortField.EMAIL, SortDirection.DESC),
        ("id; DROP TABLE comments", SortField.CREATED_AT, SortDirection.DESC),
    ],
)
def test_ordering_parse(raw: str | None, field: SortField, direction: SortDirection) -> None:
    ordering = Ordering.parse(raw)
    assert (ordering.field, ordering.direction) == (field, direction)


def test_child_path_sorts_depth_first() -> None:
    root = child_path("", 1)
    a = child_path(root, 2)
    a_reply = child_path(a, 10)
    b = child_path(root, 3)
    assert sorted([b, a_reply, a, root]) == [root, a, a_reply, b]


def test_upload_detects_by_magic_bytes() -> None:
    assert Upload("x.png", b"\x89PNG\r\n\x1a\n...").detect_kind() is AttachmentKind.IMAGE
    assert Upload("notes.TXT", "привіт".encode()).detect_kind() is AttachmentKind.TEXT
    with pytest.raises(AttachmentError):
        Upload("evil.png", b"<?php echo 1; ?>").detect_kind()
    with pytest.raises(AttachmentError):
        Upload("big.txt", b"a" * (100 * 1024 + 1)).detect_kind()
    with pytest.raises(AttachmentError):
        Upload("x.exe", b"MZ").detect_kind()
