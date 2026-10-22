# Usage: python frontend/scripts/make_icons.py frontend/public  (needs Pillow)
"""Generates brand raster assets (icons, OG image) from the same geometry as favicon.svg."""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

out = sys.argv[1]
VIOLET, MINT, INK, PAPER = (109, 74, 255), (61, 220, 168), (30, 27, 75), (241, 242, 251)

def mark(size, pad=0.0, radius=0.28, bg=VIOLET):
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    inset = int(s * pad)
    d.rounded_rectangle((inset, inset, s - inset, s - inset), radius=int((s - 2 * inset) * radius), fill=bg)
    k = (s - 2 * inset) / 32
    ox = oy = inset
    w = int(3 * k)
    # path M10 7 v10 a5 5 0 0 0 5 5 h7
    d.line([(ox + 10 * k, oy + 7 * k), (ox + 10 * k, oy + 17 * k)], fill="white", width=w)
    d.arc((ox + 10 * k - 0, oy + 12 * k, ox + 20 * k, oy + 22 * k), 90, 180, fill="white", width=w)
    d.line([(ox + 15 * k, oy + 22 * k - w / 2 + w / 2), (ox + 22 * k, oy + 22 * k)], fill="white", width=w)
    for x, y in [(10, 7)]:
        d.ellipse((ox + x * k - w / 2, oy + y * k - w / 2, ox + x * k + w / 2, oy + y * k + w / 2), fill="white")
    d.ellipse((ox + 20 * k, oy + 19 * k, ox + 26 * k, oy + 25 * k), fill=MINT)
    return img.resize((size, size), Image.LANCZOS)

mark(192).save(f"{out}/icon-192.png")
mark(512).save(f"{out}/icon-512.png")
mark(512, pad=0.12, radius=0.0, bg=VIOLET).convert("RGB").save(f"{out}/icon-512-maskable.png")
apple = Image.new("RGB", (180, 180), VIOLET); apple.paste(mark(180, radius=0.0), (0, 0), mark(180, radius=0.0)); apple.save(f"{out}/apple-touch-icon.png")

# Open Graph card 1200x630
W, H = 1200, 630
og = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(og)
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse((700, -200, 1400, 500), fill=(165, 139, 255, 120))
og.paste(glow.filter(ImageFilter.GaussianBlur(120)), (0, 0), glow.filter(ImageFilter.GaussianBlur(120)))
d = ImageDraw.Draw(og)
# rails
d.line([(120, 120), (120, 330)], fill=VIOLET, width=14)
d.arc((120, 260, 260, 400), 90, 180, fill=VIOLET, width=14)
d.line([(190, 400), (330, 400)], fill=VIOLET, width=14)
d.line([(260, 400), (260, 470)], fill=(165, 139, 255), width=14)
d.arc((260, 400, 400, 540), 90, 180, fill=(165, 139, 255), width=14)
d.line([(330, 540), (430, 540)], fill=(165, 139, 255), width=14)
d.ellipse((318, 382, 354, 418), fill=VIOLET)
d.ellipse((420, 522, 456, 558), fill=MINT)
try:
    big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Black.ttf", 92)
    small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 38)
except OSError:
    big = ImageFont.load_default(size=92); small = ImageFont.load_default(size=38)
d.text((520, 170), "Threadline", font=big, fill=INK)
d.text((524, 300), "Обговорення, що ростуть гілками.", font=small, fill=INK)
d.text((524, 352), "Відповіді будь-якої глибини · наживо", font=small, fill=(95, 98, 131))
mark(120).convert("RGBA")
og.paste(mark(110), (1030, 470), mark(110))
og.save(f"{out}/og-image.png", optimize=True)
print("ok")
