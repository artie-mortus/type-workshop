"""Build the project icons from DejaVu Serif Bold glyph outlines.

Writes icon.svg, favicon.ico, and apple-touch-icon.png to the project root.
Needs fontTools, rsvg-convert, and ImageMagick (magick).
Run from anywhere: python3 scripts/make-icon.py
"""
import pathlib
import subprocess
import tempfile
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

FONT = "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf"
f = TTFont(FONT); gs = f.getGlyphSet(); cmap = f.getBestCmap()

def outline(text, kern=0):
    x = 0; parts = []
    for ch in text:
        parts.append((cmap[ord(ch)], x)); x += gs[cmap[ord(ch)]].width + kern
    bp = BoundsPen(gs)
    for g, dx in parts:
        gs[g].draw(TransformPen(bp, (1,0,0,1,dx,0)))
    return parts, bp.bounds

def svg_path(parts, scale, tx, ty):
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    for g, dx in parts:
        # font units are y-up; flip into SVG space
        gs[g].draw(TransformPen(pen, (scale, 0, 0, -scale, tx + dx*scale, ty)))
    return pen.getCommands()

parts, (x0, y0, x1, y1) = outline("Ab", kern=-120)
width = 48
scale = width / (x1 - x0)
baseline = 38
tx = (64 - width) / 2 - x0*scale
d = svg_path(parts, scale, tx, baseline)

def icon_svg(radius):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="{radius}" fill="#25344d"/>
<path fill="#a8bde9" d="{d}"/>
<path fill="none" stroke="#c5a0eb" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" d="M15 49H49M20 44l-5 5 5 5M44 44l5 5-5 5"/>
</svg>
'''

root = pathlib.Path(__file__).resolve().parent.parent
(root / "icon.svg").write_text(icon_svg(14))

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    # iOS applies its own corner mask, so the touch icon stays square.
    square = tmp / "square.svg"
    square.write_text(icon_svg(0))
    subprocess.run(["rsvg-convert", "-w", "180", "-h", "180", str(square),
                    "-o", str(root / "apple-touch-icon.png")], check=True)
    sizes = []
    for size in (16, 32, 48):
        png = tmp / f"{size}.png"
        subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size),
                        str(root / "icon.svg"), "-o", str(png)], check=True)
        sizes.append(str(png))
    subprocess.run(["magick", *sizes, str(root / "favicon.ico")], check=True)
