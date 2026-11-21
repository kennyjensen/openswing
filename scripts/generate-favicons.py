"""Export bookmark icons from the existing Daedalus SVG (no solver required).

Optional asset-maintenance command: python3 scripts/generate-favicons.py
Requires Pillow and PyMuPDF. Generated icons are committed, so builds and
GitHub Actions do not need these image-export dependencies.
"""
from pathlib import Path
import math
import re
import xml.etree.ElementTree as ET

from PIL import Image
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'public'
original = (PUBLIC / 'openswing-logo.svg').read_text()
paths = ET.fromstring(original).findall('.//{http://www.w3.org/2000/svg}path')
angle = math.radians(20)
points = []
for path in paths:
    for x, y in re.findall(r'(-?[\d.]+),(-?[\d.]+)', path.attrib['d']):
        x, y = float(x), float(y)
        points.append((x * math.cos(angle) - y * math.sin(angle),
                       x * math.sin(angle) + y * math.cos(angle)))
x, y = zip(*points)
cx, cy = (min(x) + max(x)) / 2, (min(y) + max(y)) / 2
scale = 52 / max(max(x) - min(x), max(y) - min(y))
group = original[original.index('  <g '):original.rindex('</svg>')].strip()
# Stronger outlines keep the original plot colors legible at 16 pixels.
group = re.sub(r'stroke-width="[\d.]+"', 'stroke-width="1.8"', group)
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <title>OpenSwing</title>
  <rect width="64" height="64" rx="12" fill="#101719"/>
  <g transform="translate(32 32) scale({scale:.8f}) translate({-cx:.8f} {-cy:.8f}) rotate(20)">
    {group}
  </g>
</svg>
'''
(PUBLIC / 'favicon.svg').write_text(svg)
document = pymupdf.open(stream=svg.encode(), filetype='svg')
pdf = pymupdf.open('pdf', document.convert_to_pdf())
pixels = pdf[0].get_pixmap(matrix=pymupdf.Matrix(8, 8), alpha=True)
image = Image.frombytes('RGBA', (pixels.width, pixels.height), pixels.samples)
for size, name in [(180, 'apple-touch-icon.png'), (192, 'openswing-icon-192.png'), (512, 'openswing-icon-512.png')]:
    image.resize((size, size), Image.Resampling.LANCZOS).save(PUBLIC / name, optimize=True)
image.save(PUBLIC / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)], bitmap_format='bmp')
pdf.close()
document.close()
print('Generated SVG, ICO, Apple touch icon and 192/512-pixel app icons.')
