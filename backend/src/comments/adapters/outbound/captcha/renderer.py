from __future__ import annotations

import io
import secrets

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 200, 64
_rand = secrets.SystemRandom()


class PillowCaptchaRenderer:
    """Distorted text: per-glyph rotation and jitter, noise curves and dots.

    Rendered on a transparent background so the UI can sit it on any theme.
    """

    def __init__(self, font_size: int = 38) -> None:
        self._font = ImageFont.load_default(size=font_size)

    def render(self, text: str) -> bytes:
        image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        for _ in range(4):
            self._noise_curve(draw)

        step = (WIDTH - 24) / len(text)
        for index, char in enumerate(text):
            glyph = Image.new("RGBA", (56, 64), (0, 0, 0, 0))
            ImageDraw.Draw(glyph).text((10, 6), char, font=self._font, fill=self._ink())
            glyph = glyph.rotate(_rand.uniform(-28, 28), resample=Image.Resampling.BICUBIC, expand=False)
            x = int(10 + index * step + _rand.uniform(-3, 3))
            y = int(_rand.uniform(-6, 4))
            image.alpha_composite(glyph, (x, y))

        for _ in range(140):
            draw.point((_rand.randrange(WIDTH), _rand.randrange(HEIGHT)), fill=self._ink(alpha=150))
        image = image.filter(ImageFilter.SMOOTH)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    @staticmethod
    def _ink(alpha: int = 255) -> tuple[int, int, int, int]:
        # Violet-to-teal range, readable on light and dark backgrounds.
        return (_rand.randint(70, 130), _rand.randint(60, 150), _rand.randint(170, 240), alpha)

    def _noise_curve(self, draw: ImageDraw.ImageDraw) -> None:
        points = [(x, HEIGHT / 2 + _rand.uniform(-22, 22)) for x in range(0, WIDTH + 40, 40)]
        draw.line(points, fill=self._ink(alpha=170), width=2, joint="curve")
