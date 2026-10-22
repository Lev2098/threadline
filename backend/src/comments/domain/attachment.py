from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from comments.domain.errors import AttachmentError

IMAGE_MAX_WIDTH = 320
IMAGE_MAX_HEIGHT = 240
TEXT_FILE_MAX_BYTES = 100 * 1024
# Raw upload cap for images: they are downscaled anyway, this only stops abuse.
IMAGE_UPLOAD_MAX_BYTES = 10 * 1024 * 1024


class AttachmentKind(StrEnum):
    IMAGE = "image"
    TEXT = "text"


class ImageFormat(StrEnum):
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"


# Magic bytes decide the type, never the file name or the client's Content-Type.
_SIGNATURES: tuple[tuple[bytes, ImageFormat], ...] = (
    (b"\xff\xd8\xff", ImageFormat.JPEG),
    (b"\x89PNG\r\n\x1a\n", ImageFormat.PNG),
    (b"GIF87a", ImageFormat.GIF),
    (b"GIF89a", ImageFormat.GIF),
)


@dataclass(frozen=True, slots=True)
class Upload:
    """Raw file as received from the client."""

    filename: str
    content: bytes

    @property
    def extension(self) -> str:
        return self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""

    def detect_kind(self) -> AttachmentKind:
        if self.extension in {"jpg", "jpeg", "png", "gif"}:
            if self.image_format() is None:
                raise AttachmentError("File content is not a JPG, GIF or PNG image.", field="attachment")
            if len(self.content) > IMAGE_UPLOAD_MAX_BYTES:
                raise AttachmentError("Image is too large to process (max 10 MB).", field="attachment")
            return AttachmentKind.IMAGE
        if self.extension == "txt":
            self._check_text()
            return AttachmentKind.TEXT
        raise AttachmentError("Only JPG, GIF, PNG images or TXT files are allowed.", field="attachment")

    def image_format(self) -> ImageFormat | None:
        for signature, fmt in _SIGNATURES:
            if self.content.startswith(signature):
                return fmt
        return None

    def _check_text(self) -> None:
        if len(self.content) > TEXT_FILE_MAX_BYTES:
            raise AttachmentError("Text file must not exceed 100 KB.", field="attachment")
        if b"\x00" in self.content:
            raise AttachmentError("Text file must not contain binary data.", field="attachment")
        try:
            self.content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AttachmentError("Text file must be UTF-8 encoded.", field="attachment") from exc


@dataclass(frozen=True, slots=True)
class Attachment:
    kind: AttachmentKind
    path: str
    original_name: str
    size: int
    width: int | None = None
    height: int | None = None
