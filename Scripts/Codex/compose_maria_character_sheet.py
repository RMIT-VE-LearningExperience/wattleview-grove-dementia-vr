"""Compose Maria's in-engine Unreal renders into a presentation-ready character sheet."""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


SOURCE = Path(r"D:\Unreal-Projects\WattleviewGrove-ue58\Saved\Captures\CharacterSheet\Maria")
OUTPUT = SOURCE.parent / "Maria_Character_Sheet.png"
W, H = 3840, 2160

BG_TOP = (25, 29, 34)
BG_BOTTOM = (12, 15, 19)
CARD = (30, 35, 41)
CARD_LIGHT = (39, 45, 52)
TEXT = (244, 240, 231)
MUTED = (170, 177, 183)
ACCENT = (191, 166, 116)
BLUE = (83, 99, 160)


def font(name, size):
    return ImageFont.truetype(str(Path(r"C:\Windows\Fonts") / name), size)


FONT_TITLE = font("segoeuib.ttf", 92)
FONT_SUB = font("segoeui.ttf", 30)
FONT_LABEL = font("segoeuib.ttf", 31)
FONT_SMALL = font("segoeui.ttf", 24)
FONT_DETAIL = font("segoeui.ttf", 27)
FONT_DETAIL_BOLD = font("segoeuib.ttf", 27)


def gradient_background():
    image = Image.new("RGB", (W, H))
    px = image.load()
    for y in range(H):
        t = y / max(1, H - 1)
        color = tuple(round(a * (1 - t) + b * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        for x in range(W):
            px[x, y] = color
    return image


def rounded_card(canvas, box, radius=22, fill=CARD, outline=(61, 68, 74), width=2):
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def subject_cutout(path, threshold=12):
    image = Image.open(path).convert("RGBA")
    r, g, b, _ = image.split()
    peak = ImageChops.lighter(ImageChops.lighter(r, g), b)
    # The capture backdrop is near-black. A narrow soft transition retains dark shoes,
    # skin shadows and hair antialiasing without carrying the rectangular backdrop.
    mask = peak.point(lambda p: max(0, min(255, (p - threshold) * 50)))
    bbox = mask.getbbox()
    if bbox is None:
        return image
    pad = 20
    bbox = (
        max(0, bbox[0] - pad),
        max(0, bbox[1] - pad),
        min(image.width, bbox[2] + pad),
        min(image.height, bbox[3] + pad),
    )
    image = image.crop(bbox)
    image.putalpha(mask.crop(bbox))
    return image


def contain(image, width, height):
    scale = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def paste_with_shadow(canvas, image, center_x, bottom_y, max_w, max_h, shadow_alpha=120):
    fitted = contain(image, max_w, max_h)
    x = round(center_x - fitted.width / 2)
    y = round(bottom_y - fitted.height)
    alpha = fitted.getchannel("A")
    shadow = Image.new("RGBA", fitted.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(18)).point(lambda p: p * shadow_alpha // 255))
    canvas.alpha_composite(shadow, (x + 18, y + 24))
    canvas.alpha_composite(fitted, (x, y))


def draw_label(draw, x, y, number, title):
    draw.text((x, y), number, font=FONT_SMALL, fill=ACCENT)
    draw.text((x + 54, y - 4), title, font=FONT_LABEL, fill=TEXT)


def main():
    canvas = gradient_background().convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # Header
    draw.text((100, 56), "MARIA RUSSO", font=FONT_TITLE, fill=TEXT)
    title_width = draw.textlength("MARIA RUSSO", font=FONT_TITLE)
    draw.rounded_rectangle((100 + title_width + 34, 93, 100 + title_width + 170, 105), 6, fill=ACCENT)
    draw.text((100, 176), "WATTLEVIEW GROVE  /  CHARACTER SHEET  /  CURRENT IN-ENGINE LOOK", font=FONT_SUB, fill=MUTED)
    draw.text(
        (100, 237),
        "RESIDENT   /   AGE 82   /   ITALIAN BACKGROUND   /   155 CM DESIGN TARGET   /   MODERATE-STAGE ALZHEIMER'S",
        font=FONT_SMALL,
        fill=ACCENT,
    )
    draw.text((3740, 86), "UE 5.8", font=FONT_LABEL, fill=ACCENT, anchor="ra")
    draw.text((3740, 140), "NEUTRAL REFERENCE POSE", font=FONT_SMALL, fill=MUTED, anchor="ra")

    view_specs = [
        ("01_front.png", "01", "FRONT"),
        ("02_three_quarter.png", "02", "THREE-QUARTER"),
        ("03_profile.png", "03", "PROFILE"),
        ("04_back.png", "04", "BACK"),
    ]
    panel_y, panel_h, panel_w, gap = 324, 1736, 620, 32
    for index, (filename, number, label) in enumerate(view_specs):
        x = 100 + index * (panel_w + gap)
        rounded_card(canvas, (x, panel_y, x + panel_w, panel_y + panel_h))
        # Small visual alignment guide.
        draw.line((x + panel_w // 2, panel_y + 90, x + panel_w // 2, panel_y + panel_h - 126), fill=(47, 53, 59), width=1)
        draw.ellipse((x + panel_w // 2 - 3, panel_y + 84, x + panel_w // 2 + 3, panel_y + 90), fill=ACCENT)
        character = subject_cutout(SOURCE / filename)
        paste_with_shadow(
            canvas,
            character,
            x + panel_w / 2,
            panel_y + panel_h - 118,
            panel_w - 68,
            panel_h - 188,
        )
        draw.rectangle((x + 28, panel_y + panel_h - 92, x + panel_w - 28, panel_y + panel_h - 90), fill=(70, 76, 82))
        draw_label(draw, x + 32, panel_y + panel_h - 68, number, label)

    # Detail column
    right_x, right_w = 2730, 1010
    face_box = (right_x, panel_y, right_x + right_w, 1190)
    rounded_card(canvas, face_box, fill=CARD_LIGHT)
    face = subject_cutout(SOURCE / "05_face.png")
    paste_with_shadow(canvas, face, right_x + right_w / 2, 1100, right_w - 90, 700, shadow_alpha=105)
    draw.rectangle((right_x + 34, 1112, right_x + right_w - 34, 1114), fill=(75, 81, 87))
    draw_label(draw, right_x + 38, 1132, "05", "FACE / NEUTRAL")

    detail_box = (right_x, 1222, right_x + right_w, panel_y + panel_h)
    rounded_card(canvas, detail_box)
    detail = subject_cutout(SOURCE / "06_outfit_detail.png")
    fitted = contain(detail, 475, 720)
    alpha = fitted.getchannel("A")
    shadow = Image.new("RGBA", fitted.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(14)).point(lambda p: p * 105 // 255))
    dx = right_x + 24
    dy = 1295
    canvas.alpha_composite(shadow, (dx + 12, dy + 16))
    canvas.alpha_composite(fitted, (dx, dy))

    copy_x = right_x + 545
    draw.text((copy_x, 1284), "CURRENT OUTFIT", font=FONT_DETAIL_BOLD, fill=ACCENT)
    draw.text(
        (copy_x, 1340),
        "Soft ivory check cardigan\nPale lace blouse\nPeriwinkle midi skirt\nBrown flat shoes",
        font=FONT_DETAIL,
        fill=TEXT,
        spacing=17,
    )
    draw.text((copy_x, 1588), "PALETTE", font=FONT_DETAIL_BOLD, fill=MUTED)
    swatches = [
        ((230, 226, 214), "IVORY"),
        ((120, 127, 137), "SILVER"),
        (BLUE, "PERIWINKLE"),
        ((86, 53, 34), "BROWN"),
    ]
    for i, (color, label) in enumerate(swatches):
        sy = 1642 + i * 72
        draw.rounded_rectangle((copy_x, sy, copy_x + 48, sy + 48), radius=10, fill=color, outline=(103, 108, 112), width=1)
        draw.text((copy_x + 68, sy + 8), label, font=FONT_SMALL, fill=TEXT)

    draw.text((right_x + 36, 1997), "06", font=FONT_SMALL, fill=ACCENT)
    draw.text((right_x + 90, 1992), "OUTFIT / MATERIAL DETAIL", font=FONT_LABEL, fill=TEXT)

    canvas.convert("RGB").save(OUTPUT, quality=96)
    print(OUTPUT)


if __name__ == "__main__":
    main()
