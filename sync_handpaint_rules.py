"""
Rebuild mask-rules.Images-handpaint.json from every unique image size under --input
(same EXIF-aware sizing as batch_inpaint_recursive / scan_image_sizes).

Run after you know all dimensions (e.g. after scan_image_sizes.py) and after saving
masks/gemini_W_H.png for each size from mask-painter.html.

  .venv\\Scripts\\python.exe sync_handpaint_rules.py --input batch-input
  .venv\\Scripts\\python.exe sync_handpaint_rules.py --input Images --rules-out mask-rules.Images-handpaint.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from scan_image_sizes import iter_images, read_size

DEFAULT_FALLBACK = {
    "w_frac": 0.16,
    "h_frac": 0.24,
    "margin_frac": 0.06,
    "pad_frac": 0.0,
}


def load_fallback_from_corner_json(path: Path) -> dict:
    if not path.is_file():
        return dict(DEFAULT_FALLBACK)
    data = json.loads(path.read_text(encoding="utf-8"))
    fb = data.get("fallback") or {}
    return {
        "w_frac": float(fb.get("w_frac", DEFAULT_FALLBACK["w_frac"])),
        "h_frac": float(fb.get("h_frac", DEFAULT_FALLBACK["h_frac"])),
        "margin_frac": float(fb.get("margin_frac", DEFAULT_FALLBACK["margin_frac"])),
        "pad_frac": float(fb.get("pad_frac", DEFAULT_FALLBACK["pad_frac"])),
    }


def build_rules(dim_counter: Counter[tuple[int, int]]) -> list[dict]:
    rules: list[dict] = []
    for (w, h), _ in sorted(dim_counter.items(), key=lambda x: (-x[1], -x[0][0] * x[0][1])):
        rules.append(
            {
                "if": {
                    "width_min": w,
                    "width_max": w,
                    "height_min": h,
                    "height_max": h,
                },
                "then": {"mask": f"masks/gemini_{w}_{h}.png"},
            }
        )
    return rules


def main() -> None:
    ap = argparse.ArgumentParser(description="Write handpaint JSON for every unique image size under a folder.")
    ap.add_argument("--input", type=Path, required=True, help="Folder to scan (recursive)")
    ap.add_argument(
        "--rules-out",
        type=Path,
        default=Path("mask-rules.Images-handpaint.json"),
        help="Output JSON path",
    )
    ap.add_argument(
        "--fallback-from",
        type=Path,
        default=Path("mask-rules.Images-default.json"),
        help="Read fallback corner block from this JSON if present",
    )
    args = ap.parse_args()

    root = args.input.resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    paths = iter_images(root)
    if not paths:
        raise SystemExit(f"No images under {root}")

    dim_counter: Counter[tuple[int, int]] = Counter()
    for p in paths:
        w, h = read_size(p)
        dim_counter[(w, h)] += 1

    out = {
        "fallback": load_fallback_from_corner_json(args.fallback_from.resolve()),
        "rules": build_rules(dim_counter),
    }

    args.rules_out.parent.mkdir(parents=True, exist_ok=True)
    args.rules_out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(f"Scanned {len(paths)} images, {len(dim_counter)} unique sizes -> {args.rules_out.resolve()}")
    for (w, h), c in sorted(dim_counter.items(), key=lambda x: (-x[1], -x[0][0] * x[0][1])):
        print(f"  {w}x{h}  count={c}  -> masks/gemini_{w}_{h}.png")


if __name__ == "__main__":
    main()
