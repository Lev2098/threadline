"""Comment markup: a tiny allow-listed XHTML dialect.

The brief asks for regex-based validation with a tag-closing check and valid
XHTML output. The approach is *parse, validate, re-serialize*:

1. a regex tokenizer splits the input into tags and text;
2. every tag is checked against the allow-list, every attribute value is
   validated (``href`` only with safe schemes);
3. a stack verifies that tags are properly nested and closed;
4. the output is rebuilt from tokens, so nothing the user typed reaches the
   page verbatim: text is escaped, attributes are re-quoted.

Because the output is generated rather than filtered, XSS payloads such as
``<a href="javascript:...">`` or ``<i onclick=...>`` can't survive.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from comments.domain.errors import MarkupError

TEXT_MAX = 5000

ALLOWED_TAGS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "title"}),
    "code": frozenset(),
    "i": frozenset(),
    "strong": frozenset(),
}
_SAFE_HREF_RE = re.compile(r"^(?:https?://|mailto:)[^\s\"'<>`]+$", re.IGNORECASE)

# Anything that looks like a tag: <name ...>, </name>, <name/>. As in HTML, "< b" is text.
_TAG_RE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9]*)\b([^<>]*?)(/?)\s*>")
_XML_ILLEGAL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffe\uffff]")
# Zero-width and similar characters: a text made only of these is "empty".
_INVISIBLE_RE = re.compile("[\u200b-\u200f\u2060\ufeff\u00ad]")
# Only well-formed references ("&amp;", "&#169;"); "&copy=2" in a URL stays literal text.
_ENTITY_RE = re.compile(r"&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_ATTR_RE = re.compile(r"""([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)')""")


@dataclass(frozen=True, slots=True)
class CommentText:
    """User text in two forms: raw source and sanitized XHTML."""

    source: str
    html: str

    @classmethod
    def parse(cls, source: str) -> CommentText:
        source = (source or "").replace("\r\n", "\n").replace("\r", "\n")
        # Characters that are illegal in XML would make the output invalid XHTML.
        source = _XML_ILLEGAL_RE.sub("", source).strip()
        if not _INVISIBLE_RE.sub("", source).strip():
            raise MarkupError("Text is required.", field="text")
        if len(source) > TEXT_MAX:
            raise MarkupError(f"Text must be at most {TEXT_MAX} characters.", field="text")
        return cls(source=source, html=_render(source))

    @property
    def plain(self) -> str:
        """Text without tags, used for search indexing and quote previews."""
        return html.unescape(_TAG_RE.sub("", self.html))


def _render(source: str) -> str:
    out: list[str] = []
    stack: list[str] = []
    pos = 0

    for match in _TAG_RE.finditer(source):
        out.append(_escape_text(source[pos : match.start()]))
        pos = match.end()

        closing, name, attrs_src, self_closing = match.groups()
        name = name.lower()
        if name not in ALLOWED_TAGS:
            raise MarkupError(f"Tag <{name}> is not allowed. Allowed tags: a, code, i, strong.", field="text")
        if self_closing:
            raise MarkupError(f"Tag <{name}> must have a closing tag.", field="text")

        if closing:
            if attrs_src.strip():
                raise MarkupError(f"Closing tag </{name}> cannot have attributes.", field="text")
            if not stack:
                raise MarkupError(f"Closing tag </{name}> has no matching opening tag.", field="text")
            if stack[-1] != name:
                raise MarkupError(f"Expected </{stack[-1]}> but found </{name}>.", field="text")
            stack.pop()
            out.append(f"</{name}>")
            continue

        if name == "a" and "a" in stack:
            raise MarkupError("Links cannot be nested.", field="text")
        out.append(_open_tag(name, attrs_src))
        stack.append(name)

    out.append(_escape_text(source[pos:]))
    if stack:
        raise MarkupError(f"Tag <{stack[-1]}> is not closed.", field="text")
    return "".join(out)


def _open_tag(name: str, attrs_src: str) -> str:
    allowed = ALLOWED_TAGS[name]
    attrs: dict[str, str] = {}

    leftover = _ATTR_RE.sub("", attrs_src).strip()
    if leftover:
        raise MarkupError(f"Malformed attributes in <{name}>: values must be quoted.", field="text")
    for attr_match in _ATTR_RE.finditer(attrs_src):
        attr = attr_match.group(1).lower()
        value = attr_match.group(2) if attr_match.group(2) is not None else attr_match.group(3)
        if attr not in allowed:
            raise MarkupError(f"Attribute '{attr}' is not allowed in <{name}>.", field="text")
        if attr in attrs:
            raise MarkupError(f"Duplicate attribute '{attr}' in <{name}>.", field="text")
        attrs[attr] = _unescape(value).strip()

    if name == "a":
        href = attrs.get("href", "")
        if not _SAFE_HREF_RE.fullmatch(href):
            raise MarkupError("Link href must start with http://, https:// or mailto:.", field="text")
        attrs["rel"] = "nofollow noopener noreferrer"
        attrs["target"] = "_blank"

    rendered = "".join(f' {key}="{html.escape(val, quote=True)}"' for key, val in attrs.items())
    return f"<{name}{rendered}>"


def _unescape(text: str) -> str:
    """Decode only complete character references, never legacy ``&copy`` without ';'."""
    decoded = _ENTITY_RE.sub(lambda m: html.unescape(m.group(0)), text)
    return _XML_ILLEGAL_RE.sub("", decoded)


def _escape_text(text: str) -> str:
    # html.escape turns a stray "<" or "&" into entities, keeping output valid XHTML.
    return html.escape(_unescape(text), quote=False)
