from __future__ import annotations

import io

from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from comments.application.ports import ProcessedImage
from comments.domain.attachment import ImageFormat
from comments.domain.errors import AttachmentError

# Decompression-bomb guards, checked from the header before any pixel is decoded.
# (Pillow's own MAX_IMAGE_PIXELS only *warns* between 1x and 2x the limit.)
MAX_PIXELS = 40_000_000
MAX_GIF_FRAMES = 100
MAX_GIF_TOTAL_PIXELS = 50_000_000  # frames x width x height
Image.MAX_IMAGE_PIXELS = MAX_PIXELS * 2

# MPO = multi-picture JPEG produced by many phone cameras; stored as plain JPEG.
_FORMATS = {"JPEG": ImageFormat.JPEG, "MPO": ImageFormat.JPEG, "PNG": ImageFormat.PNG, "GIF": ImageFormat.GIF}


class PillowImageProcessor:
    def fit(self, content: bytes, max_width: int, max_height: int) -> ProcessedImage:
        try:
            image = Image.open(io.BytesIO(content))
            fmt = _FORMATS.get(image.format or "")
            if fmt is None:
                raise AttachmentError("Only JPG, GIF and PNG images are allowed.", field="attachment")
            if image.width * image.height > MAX_PIXELS:
                raise AttachmentError("The image is too large (max 40 megapixels).", field="attachment")
            if fmt is ImageFormat.GIF and getattr(image, "is_animated", False):
                frames = getattr(image, "n_frames", 1)
                if frames > MAX_GIF_FRAMES or frames * image.width * image.height > MAX_GIF_TOTAL_PIXELS:
                    raise AttachmentError("The animation is too long or too large.", field="attachment")
                return self._fit_animated(image, max_width, max_height)
            return self._fit_still(image, fmt, max_width, max_height)
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
            raise AttachmentError("The image is damaged or too large.", field="attachment") from exc

    @staticmethod
    def _fit_still(image: Image.Image, fmt: ImageFormat, max_w: int, max_h: int) -> ProcessedImage:
        image = ImageOps.exif_transpose(image)  # respect camera rotation, then drop EXIF
        image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)  # proportional, never upscales
        buffer = io.BytesIO()
        if fmt is ImageFormat.JPEG:
            image.convert("RGB").save(buffer, "JPEG", quality=86, optimize=True, progressive=True)
        elif fmt is ImageFormat.PNG:
            image.save(buffer, "PNG", optimize=True)
        else:
            image.save(buffer, "GIF", optimize=True)
        return ProcessedImage(buffer.getvalue(), image.width, image.height, fmt)

    @staticmethod
    def _fit_animated(image: Image.Image, max_w: int, max_h: int) -> ProcessedImage:
        frames = []
        durations = []
        for frame in ImageSequence.Iterator(image):
            copy = frame.convert("RGBA")
            copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            frames.append(copy)
            durations.append(frame.info.get("duration", 100))
        buffer = io.BytesIO()
        frames[0].save(
            buffer,
            "GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=image.info.get("loop", 0),
            disposal=2,
            optimize=True,
        )
        return ProcessedImage(buffer.getvalue(), frames[0].width, frames[0].height, ImageFormat.GIF)
