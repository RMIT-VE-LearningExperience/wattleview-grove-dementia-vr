"""Readout texture for SM_DayDateClock's screen (Export/T_DayDateClock_Screen.png, 1024 x 512).

Run with any Python that has Pillow:  python make_clock_screen.py
White on black, laid out like a real dementia day/date clock. The screen face on the mesh is about
17.96 x 11.16 cm (aspect 1.61) while the image is 2:1, so the layout is drawn on an 824 x 512 canvas
and stretched to 1024 wide: the letters look correctly proportioned on the mesh.
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\Unreal-Projects\WattleviewGrove-ue58\SourceArt\Room\Export\T_DayDateClock_Screen.png"
FONTS = r"C:\Windows\Fonts"
W, H = 824, 512
LINES = [("MONDAY", "arialbd.ttf", 150, 30), ("MORNING", "arialbd.ttf", 74, 205),
         ("26 OCTOBER 2026", "arial.ttf", 62, 312), ("9:30 AM", "arial.ttf", 62, 405)]

img = Image.new("RGB", (W, H), (0, 0, 0))
d = ImageDraw.Draw(img)
for text, font, size, y in LINES:
    f = ImageFont.truetype(os.path.join(FONTS, font), size)
    while d.textlength(text, font=f) > W - 50:
        size -= 2
        f = ImageFont.truetype(os.path.join(FONTS, font), size)
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text, font=f, fill=(255, 255, 255))
d.line([(60, 190), (W - 60, 190)], fill=(90, 90, 90), width=3)
img = img.resize((1024, 512), Image.LANCZOS)
img.save(OUT)
print("wrote", OUT)
