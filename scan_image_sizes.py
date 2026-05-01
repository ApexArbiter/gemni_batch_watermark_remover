"""
List image pixel sizes under a folder (recursive). Uses EXIF transpose like the batch inpainter.

Examples:
  .venv\\Scripts\\python.exe scan_image_sizes.py --input Images
  .venv\\Scripts\\python.exe scan_image_sizes.py --input batch-input --csv sizes.csv
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def iter_images(root: Path) -> list[Path]:
    root = root.resolve()
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES:
            out.append(p.resolve())
    return out


def read_size(path: Path) -> tuple[int, int]:
    im = Image.open(path)
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    w, h = im.size
    return w, h


def main() -> None:
    ap = argparse.ArgumentParser(description="Report width×height for images under a folder.")
    ap.add_argument(
        "--input",
        type=Path,
        default=Path("Images"),
        help="Root folder (default: Images)",
    )
    ap.add_argument("--csv", type=Path, default=None, help="Write path,width,height,aspect rows")
    args = ap.parse_args()

    root = args.input.resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}")
        raise SystemExit(1)

    paths = iter_images(root)
    if not paths:
        print(f"No images under {root}")
        raise SystemExit(0)

    rows: list[tuple[str, int, int, float]] = []
    dim_counter: Counter[tuple[int, int]] = Counter()

    for p in paths:
        w, h = read_size(p)
        ar = w / h if h else 0.0
        rel = p.relative_to(root).as_posix()
        rows.append((rel, w, h, ar))
        dim_counter[(w, h)] += 1

    print(f"Scanned {len(paths)} images under {root}\n")
    print(f"{'w':>5} {'h':>5} {'aspect':>8}  path")
    print("-" * 72)
    for rel, w, h, ar in sorted(rows, key=lambda r: (-r[1] * r[2], r[0])):
        print(f"{w:5d} {h:5d} {ar:8.4f}  {rel}")

    print("\n-- Unique dimensions (count) --")
    for (w, h), c in dim_counter.most_common():
        print(f"  {w}x{h}  count={c}")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            wcsv = csv.writer(f)
            wcsv.writerow(["path", "width", "height", "aspect"])
            wcsv.writerows(rows)
        print(f"\nWrote {args.csv.resolve()}")


if __name__ == "__main__":
    main()
