"""
Build grayscale PNG masks (white = inpaint) at each canonical photo size, using the
same corner fractions your mask-rules JSON would pick for that size.

Edit the PNGs in IOPaint Web UI (or any editor): paint extra white wherever the Gemini
logo still appears, then batch with mask-rules.Images-handpaint.json.

Usage:
  .venv\\Scripts\\python.exe generate_hand_paint_masks.py
  .venv\\Scripts\\python.exe generate_hand_paint_masks.py --rules mask-rules.Images-default.json --out masks
  .venv\\Scripts\\python.exe generate_hand_paint_masks.py --inflate 1.25
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from make_corner_mask import build_corner_mask_array
from mask_rules import MaskRules


# Representative sizes from your scan (1428x779 uses 1431x780 mask via resize in batch).
DEFAULT_CANONICAL: list[tuple[int, int]] = [
    (626, 626),
    (1024, 1024),
    (1280, 698),
    (1431, 780),
    (1600, 872),
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate starter corner masks per bucket for hand-painting.")
    ap.add_argument("--rules", type=Path, default=Path("mask-rules.Images-default.json"))
    ap.add_argument("--out", type=Path, default=Path("masks"))
    ap.add_argument(
        "--inflate",
        type=float,
        default=1.0,
        help="Multiply w_frac and h_frac on templates only (e.g. 1.2 = bigger white starter).",
    )
    ap.add_argument(
        "--sizes",
        type=str,
        default="",
        help='Optional: "626x626,1024x1024,1280x698" overrides canonical sizes.',
    )
    args = ap.parse_args()

    rules_path = args.rules.resolve()
    if not rules_path.is_file():
        raise SystemExit(f"Rules file not found: {rules_path}")

    rules = MaskRules.load(rules_path)
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.sizes.strip():
        pairs: list[tuple[int, int]] = []
        for part in args.sizes.split(","):
            part = part.strip().lower().replace(" ", "")
            if "x" not in part:
                continue
            a, b = part.split("x", 1)
            pairs.append((int(a), int(b)))
        canonical = pairs
    else:
        canonical = DEFAULT_CANONICAL

    note = out_dir / "HANDPAINT_STEPS.txt"
    lines = [
        "Starter masks use the same bottom-right rectangles as your corner rules JSON.",
        "If LaMa still misses the logo:",
        "  1) Open each PNG in IOPaint Web UI (brush white on the watermark).",
        "  2) Save over the same file in this folder.",
        '  3) Set MASK_RULES_JSON to mask-rules.Images-handpaint.json in the batch .bat files.',
        "",
        "Generated files:",
    ]

    inflate = max(0.5, float(args.inflate))

    for w, h in canonical:
        tmpl, corner = rules.resolve(w, h)
        if tmpl is not None:
            raise SystemExit(f"Rule for {w}x{h} returned a PNG mask — use corner-based JSON as --rules.")
        assert corner is not None
        wf, hf, mf, pf = corner
        wf *= inflate
        hf *= inflate
        arr = build_corner_mask_array(w, h, wf, hf, mf, pf)
        fname = f"gemini_{w}_{h}.png"
        dest = out_dir / fname
        Image.fromarray(arr, mode="L").save(dest)
        lines.append(f"  {fname}")
        nz = int((arr >= 127).sum())
        print(f"Wrote {dest}  ({w}x{h}, white pixels ~{nz})")

    note.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {note}")


if __name__ == "__main__":
    main()
