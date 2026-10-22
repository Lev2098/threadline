import pytest

from comments.domain.errors import MarkupError
from comments.domain.markup import TEXT_MAX, CommentText


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("plain text", "plain text"),
        ("<i>it</i> and <strong>bold</strong>", "<i>it</i> and <strong>bold</strong>"),
        ("<code>x = 1</code>", "<code>x = 1</code>"),
        ("<STRONG>upper</STRONG>", "<strong>upper</strong>"),
        ("a < b && c > d", "a &lt; b &amp;&amp; c &gt; d"),
        ("<i><strong>nested</strong></i>", "<i><strong>nested</strong></i>"),
        (
            '<a href="https://example.com" title="Ex">link</a>',
            '<a href="https://example.com" title="Ex" rel="nofollow noopener noreferrer" target="_blank">link</a>',
        ),
        (
            "<a href='mailto:me@x.io'>mail</a>",
            '<a href="mailto:me@x.io" rel="nofollow noopener noreferrer" target="_blank">mail</a>',
        ),
        ('<a title="&quot;q&quot;" href="http://x.io">q</a>', None),
    ],
)
def test_valid_markup_is_reserialized(source: str, expected: str | None) -> None:
    result = CommentText.parse(source).html
    if expected is not None:
        assert result == expected
    else:
        assert 'title="&quot;q&quot;"' in result


@pytest.mark.parametrize(
    ("source", "message_part"),
    [
        ("<script>alert(1)</script>", "not allowed"),
        ("<img src=x onerror=alert(1)>", "not allowed"),
        ('<i onclick="alert(1)">x</i>', "not allowed"),
        ('<a href="javascript:alert(1)">x</a>', "href"),
        ('<a href=" JaVaScRiPt:alert(1)">x</a>', "href"),
        ('<a href="data:text/html,x">x</a>', "href"),
        ("<a>no href</a>", "href"),
        ("<a href=https://x.io>x</a>", "quoted"),
        ("<i>unclosed", "not closed"),
        ("<i><strong>bad</i></strong>", "Expected </strong>"),
        ("stray </i>", "no matching"),
        ("<i/>", "closing tag"),
        ('<a href="https://a.io"><a href="https://b.io">x</a></a>', "nested"),
        ("", "required"),
        ("   ", "required"),
    ],
)
def test_invalid_markup_is_rejected(source: str, message_part: str) -> None:
    with pytest.raises(MarkupError) as exc:
        CommentText.parse(source)
    assert message_part in exc.value.message
    assert exc.value.field == "text"


def test_encoded_payload_stays_encoded() -> None:
    html = CommentText.parse("&lt;script&gt;alert(1)&lt;/script&gt;").html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_text_length_limit() -> None:
    with pytest.raises(MarkupError):
        CommentText.parse("x" * (TEXT_MAX + 1))


def test_plain_strips_tags() -> None:
    assert CommentText.parse("<i>a</i> &amp; <code>b</code>").plain == "a & b"
