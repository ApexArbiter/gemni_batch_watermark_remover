"""
Create a grayscale PNG mask (white = inpaint, black = keep) for a fixed bottom-right region.
IOPaint batch: one mask file is resized to each image, so the same relative corner works
if your watermark stays in the same corner across photos.

Usage:
  .venv\\Scripts\\python.exe make_corner_mask.py --from-image iopaint-input\\some.jpg -o watermark-mask.png
  .venv\\Scripts\\python.exe make_corner_mask.py --width 1920 --height 1080 -o watermark-mask.png

Tune --w-frac / --h-frac (how big the patch is toward the center).
If the logo sits *inset* from the bottom-right corner, increase those and/or --pad-frac.
Use --margin-frac for a gap between the white mask and the actual right/bottom edge of the photo.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def build_corner_mask_array(
    width: int,
    height: int,
    w_frac: float = 0.22,
    h_frac: float = 0.14,
    margin_frac: float = 0.01,
    pad_frac: float = 0.0,
) -> np.ndarray:
    """
    Grayscale mask (uint8): 255 = inpaint, 0 = keep. Bottom-right rectangle.
    Matches make_corner_mask.py / PIL rectangle (inclusive corners).
    """
    m = min(width, height)
    margin = int(max(1, margin_frac * m))
    scale = max(0.0, 1.0 + pad_frac)
    box_w = max(1, int(width * w_frac * scale))
    box_h = max(1, int(height * h_frac * scale))
    x0 = max(0, width - margin - box_w)
    y0 = max(0, height - margin - box_h)
    mask = np.zeros((height, width), dtype=np.uint8)
    x1 = width - margin
    y1 = height - margin
    if x1 >= x0 and y1 >= y0:
        mask[y0 : y1 + 1, x0 : x1 + 1] = 255
    return mask


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--output", type=Path, default=Path("watermark-mask.png"))
    p.add_argument("--from-image", type=Path, help="Match mask size to this image")
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--w-frac", type=float, default=0.22, help="White box width as fraction of image width")
    p.add_argument("--h-frac", type=float, default=0.14, help="White box height as fraction of image height")
    p.add_argument(
        "--pad-frac",
        type=float,
        default=0.0,
        help="Grow width/height by this fraction after w/h-frac (e.g. 0.25 = 25%% larger patch, more space around logo)",
    )
    p.add_argument(
        "--margin-frac",
        type=float,
        default=0.01,
        help="Keep this much gap between mask edge and image right/bottom border (fraction of min(w,h))",
    )
    args = p.parse_args()

    if args.from_image:
        im = Image.open(args.from_image)
        w, h = im.size
    else:
        w, h = args.width, args.height

    arr = build_corner_mask_array(w, h, args.w_frac, args.h_frac, args.margin_frac, args.pad_frac)
    mask = Image.fromarray(arr, mode="L")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mask.save(args.output)
    if arr.any():
        ys, xs = np.where(arr >= 127)
        print(f"Wrote {args.output.resolve()} size {w}x{h} bottom-right mask ({xs.min()},{ys.min()})-({xs.max()},{ys.max()})")
    else:
        print(f"Wrote {args.output.resolve()} size {w}x{h} (warning: empty mask)")


if __name__ == "__main__":
    main()
