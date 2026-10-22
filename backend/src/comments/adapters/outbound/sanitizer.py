from __future__ import annotations

import nh3

from comments.domain.markup import ALLOWED_TAGS


class Nh3Sanitizer:
    """Defense in depth: ammonia (Rust, html5ever parser) re-checks markup that
    the domain validator has already produced. If a future change to the
    validator ever lets something through, this layer still strips it."""

    def clean(self, html: str) -> str:
        attributes = {tag: set(attrs) for tag, attrs in ALLOWED_TAGS.items()}
        attributes["a"] |= {"target"}
        return nh3.clean(
            html,
            tags=set(ALLOWED_TAGS),
            attributes=attributes,
            url_schemes={"http", "https", "mailto"},
            link_rel="nofollow noopener noreferrer",
            strip_comments=True,
        )
