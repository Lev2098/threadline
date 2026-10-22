# Usage: python frontend/scripts/make_og_image.py frontend/public  (run make_icons.py first; needs Pillow)
import math, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
out = sys.argv[1]
VIOLET, VIOLET2, MINT, INK, MUTED, PAPER = (109, 74, 255), (165, 139, 255), (61, 220, 168), (30, 27, 75), (95, 98, 131), (241, 242, 251)
W, H, S = 1200, 630, 2
img = Image.new("RGB", (W * S, H * S), PAPER)
# glow: solid colour layer + blurred alpha mask (no grey fringe)
mask = Image.new("L", img.size, 0)
ImageDraw.Draw(mask).ellipse((760 * S, -260 * S, 1500 * S, 480 * S), fill=150)
mask = mask.filter(ImageFilter.GaussianBlur(140 * S))
img.paste(Image.new("RGB", img.size, VIOLET2), (0, 0), mask)
d = ImageDraw.Draw(img)

def rail(x, y0, y1, r, x1, colour, width=14):
    pts = [(x, y0), (x, y1 - r)]
    for i in range(0, 91, 3):
        a = math.radians(180 - i)
        pts.append((x + r + r * math.cos(a), y1 - r + r * math.sin(math.radians(90 + i)) * 0 + r * math.sin(math.radians(i))))
    pts.append((x1, y1))
    d.line([(px * S, py * S) for px, py in pts], fill=colour, width=width * S, joint="curve")

rail(120, 110, 400, 70, 330, VIOLET)
rail(258, 400, 540, 70, 430, VIOLET2)
for (cx, cy, c) in [(338, 400, VIOLET), (440, 540, MINT)]:
    d.ellipse(((cx - 20) * S, (cy - 20) * S, (cx + 20) * S, (cy + 20) * S), fill=c)
d.ellipse(((120 - 7) * S, (110 - 7) * S, (120 + 7) * S, (110 + 7) * S), fill=VIOLET)
try:
    big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Black.ttf", 96 * S)
    small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 38 * S)
except OSError:
    big = ImageFont.load_default(size=96 * S); small = ImageFont.load_default(size=38 * S)
d.text((520 * S, 170 * S), "Threadline", font=big, fill=INK)
d.text((524 * S, 305 * S), "Обговорення, що ростуть гілками.", font=small, fill=INK)
d.text((524 * S, 357 * S), "Відповіді будь-якої глибини · наживо", font=small, fill=MUTED)
img = img.resize((W, H), Image.LANCZOS)
icon = Image.open(f"{out}/icon-192.png").resize((110, 110), Image.LANCZOS)
img.paste(icon, (1040, 480), icon)
img.save(f"{out}/og-image.png", optimize=True)
print("ok")
