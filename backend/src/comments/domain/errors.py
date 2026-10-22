from __future__ import annotations


class DomainError(Exception):
    """Base class for business-rule violations.

    ``field`` points to the input the error belongs to, so inbound adapters can
    map it to a form field without parsing messages.
    """

    code = "domain_error"

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class ValidationError(DomainError):
    code = "invalid"


class MarkupError(ValidationError):
    code = "invalid_markup"


class AttachmentError(ValidationError):
    code = "invalid_attachment"


class CaptchaError(ValidationError):
    code = "invalid_captcha"


class NotFoundError(DomainError):
    code = "not_found"


class InvalidInput(ValidationError):
    """Several field errors at once, so a form can highlight all of them."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("; ".join(errors.values()))
        self.errors = errors
