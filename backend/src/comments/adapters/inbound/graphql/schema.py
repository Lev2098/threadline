"""GraphQL adapter: a second inbound port over the very same use cases.

Writes with file upload stay on REST (multipart); GraphQL covers reads and
preview, which is where flexible field selection pays off.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

import strawberry
from django.core.files.storage import default_storage

from comments.application.dto import ListRootsQuery
from comments.bootstrap import container
from comments.domain.comment import Comment as DomainComment
from comments.domain.values import Ordering


@strawberry.enum
class CommentOrdering(Enum):
    CREATED_AT_DESC = "-created_at"
    CREATED_AT_ASC = "created_at"
    USERNAME_ASC = "username"
    USERNAME_DESC = "-username"
    EMAIL_ASC = "email"
    EMAIL_DESC = "-email"


@strawberry.type
class Attachment:
    kind: str
    url: str
    name: str
    size: int
    width: int | None
    height: int | None


@strawberry.type
class Comment:
    id: int
    parent_id: int | None
    root_id: int
    depth: int
    username: str
    email: str
    home_page: str | None
    html: str
    created_at: datetime
    replies_count: int
    attachment: Attachment | None

    @classmethod
    def from_domain(cls, c: DomainComment) -> Comment:
        att = c.attachment
        return cls(
            id=c.id or 0,
            parent_id=c.parent_id,
            root_id=c.root_id or 0,
            depth=c.depth,
            username=c.author.username.value,
            email=c.author.email.value,
            home_page=c.author.home_page.value if c.author.home_page else None,
            html=c.text.html,
            created_at=c.created_at or datetime.min,
            replies_count=c.replies_count,
            attachment=Attachment(
                kind=att.kind.value,
                url=default_storage.url(att.path),
                name=att.original_name,
                size=att.size,
                width=att.width,
                height=att.height,
            )
            if att
            else None,
        )


@strawberry.type
class CommentPage:
    items: list[Comment]
    page: int
    pages: int
    total: int


@strawberry.type
class Thread:
    items: list[Comment]
    next_cursor: str | None


@strawberry.type
class Query:
    @strawberry.field(description="Root comments, 25 per page.")
    def comments(self, page: int = 1, ordering: CommentOrdering = CommentOrdering.CREATED_AT_DESC) -> CommentPage:
        result = container().list_root_comments(ListRootsQuery(ordering=Ordering.parse(ordering.value), page=page))
        return CommentPage(
            items=[Comment.from_domain(c) for c in result.items],
            page=result.page,
            pages=result.pages,
            total=result.total,
        )

    @strawberry.field(description="Replies of a root comment in depth-first order.")
    def thread(self, root_id: int, cursor: str | None = None) -> Thread:
        result = container().get_thread(root_id, cursor)
        return Thread(items=[Comment.from_domain(c) for c in result.items], next_cursor=result.next_cursor)

    @strawberry.field(description="Full-text search.")
    def search(self, q: str, page: int = 1) -> CommentPage:
        result = container().search_comments(q, page)
        return CommentPage(
            items=[Comment.from_domain(c) for c in result.items],
            page=result.page,
            pages=result.pages,
            total=result.total,
        )


@strawberry.type
class Mutation:
    @strawberry.mutation(description="Validate and render text without saving it.")
    def preview_comment(self, text: str) -> str:
        return container().preview_comment(text)


schema = strawberry.Schema(query=Query, mutation=Mutation)
