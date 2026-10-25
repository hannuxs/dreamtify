"""
Membuat aset gambar brand dari assets/logo-dreamtify.png (dijalankan sekali
saat pengembangan; hasilnya di-commit ke static/img/).

- logo-dreamtify.png        : salinan asli
- logo-dreamtify-crop.png   : dipotong rapat + latar transparan (header)
- favicon-32.png, apple-touch-icon.png (180), icon-512.png, favicon.ico
"""
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "logo-dreamtify.png"
OUT = ROOT / "static" / "img"


def transparent_background(im: Image.Image, threshold: int = 244) -> Image.Image:
    """Latar putih yang tersambung ke tepi gambar dijadikan transparan."""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()

    def is_bg(x, y):
        r, g, b, _ = px[x, y]
        return r >= threshold and g >= threshold and b >= threshold

    seen = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.extend([(x, 0), (x, h - 1)])
    for y in range(h):
        q.extend([(0, y), (w - 1, y)])
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i] or not is_bg(x, y):
            continue
        seen[i] = 1
        px[x, y] = (255, 255, 255, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                q.append((nx, ny))
    return im


NAVY = (5, 42, 69, 255)  # --navy-900


def round_bottom(im: Image.Image) -> Image.Image:
    """Awan di logo terpotong tulisan; bulatkan sudut bawahnya."""
    w, h = im.size
    mask = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, -h * 4, w * 4 - 1, h * 4 - 1), radius=int(h * 4 * 0.38), fill=255
    )
    mask = mask.resize((w, h), Image.LANCZOS)
    out = im.copy()
    alpha = ImageChops.multiply(out.getchannel("A"), mask)
    out.putalpha(alpha)
    return out


def tile(cloud: Image.Image, size: int) -> Image.Image:
    """Ubin navy membulat dengan awan di tengah."""
    big = size * 4
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=int(big * 0.22), fill=NAVY
    )
    w, h = cloud.size
    scale = big * 0.84 / w
    c = cloud.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    canvas.alpha_composite(c, ((big - c.width) // 2, (big - c.height) // 2 + int(big * 0.02)))
    return canvas.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = Image.open(SRC)
    src.save(OUT / "logo-dreamtify.png", optimize=True)

    clean = transparent_background(src)
    bbox = clean.getbbox()
    pad = 6
    crop = clean.crop((bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad))
    crop.save(OUT / "logo-dreamtify-crop.png", optimize=True)

    # Ikon: bagian awan + wajah saja (di atas tulisan)
    cloud = clean.crop((100, 120, 292, 212))
    # Kikis pinggiran putih sisa anti-alias agar bersih di atas latar navy
    alpha = cloud.getchannel("A").filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(0.8))
    cloud.putalpha(alpha)
    cloud = round_bottom(cloud.crop(cloud.getbbox()))
    for name, size in (("favicon-32.png", 32), ("apple-touch-icon.png", 180), ("icon-512.png", 512)):
        img = tile(cloud, size)
        if name == "apple-touch-icon.png":
            img = img.convert("RGB")  # iOS tidak mendukung transparansi
        img.save(OUT / name, optimize=True)
    tile(cloud, 48).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("Selesai:", ", ".join(sorted(p.name for p in OUT.glob("*"))))


if __name__ == "__main__":
    main()
