"""
JSON rules: pick corner fractions or a mask PNG per image from width/height (after EXIF transpose).

Schema (rules file next to optional mask PNGs; relative "mask" paths resolve from the JSON file's directory):

{
  "fallback": { "w_frac": 0.12, "h_frac": 0.2, "margin_frac": 0.08, "pad_frac": 0 },
  "rules": [
    {
      "if": { "width_max": 1200, "height_max": 1200 },
      "then": { "w_frac": 0.22, "h_frac": 0.28, "margin_frac": 0.05, "pad_frac": 0 }
    },
    {
      "if": { "max_short_side": 900 },
      "then": { "mask": "masks/phone.png" }
    }
  ]
}

Predicates in "if" (all specified keys must pass):
  width_min, width_max, height_min, height_max,
  min_short_side, max_short_side (min(w,h)),
  min_long_side, max_long_side (max(w,h)),
  aspect_min, aspect_max (w/h as float, w>=h typical).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

CornerFracs = tuple[float, float, float, float]


def _predicates(if_block: dict[str, Any], iw: int, ih: int) -> bool:
    short = min(iw, ih)
    long_ = max(iw, ih)
    ar = iw / ih if ih else 1.0
    checks = [
        ("width_min", iw, lambda v, x: x >= v),
        ("width_max", iw, lambda v, x: x <= v),
        ("height_min", ih, lambda v, x: x >= v),
        ("height_max", ih, lambda v, x: x <= v),
        ("min_short_side", short, lambda v, x: x >= v),
        ("max_short_side", short, lambda v, x: x <= v),
        ("min_long_side", long_, lambda v, x: x >= v),
        ("max_long_side", long_, lambda v, x: x <= v),
        ("aspect_min", ar, lambda v, x: x >= v),
        ("aspect_max", ar, lambda v, x: x <= v),
    ]
    for key, value, ok in checks:
        if key not in if_block:
            continue
        bound = if_block[key]
        if not ok(bound, value):
            return False
    return True


def _then_corner(then_block: dict[str, Any]) -> CornerFracs:
    return (
        float(then_block["w_frac"]),
        float(then_block["h_frac"]),
        float(then_block["margin_frac"]),
        float(then_block.get("pad_frac", 0.0)),
    )


@dataclass
class MaskRules:
    base_dir: Path
    fallback_corner: CornerFracs
    rules: list[tuple[dict[str, Any], dict[str, Any]]]
    _mask_cache: dict[str, np.ndarray]

    @classmethod
    def load(cls, path: Path) -> MaskRules:
        path = path.resolve()
        raw = json.loads(path.read_text(encoding="utf-8"))
        base_dir = path.parent
        fb = raw.get("fallback") or {}
        fallback_corner = (
            float(fb.get("w_frac", 0.12)),
            float(fb.get("h_frac", 0.20)),
            float(fb.get("margin_frac", 0.08)),
            float(fb.get("pad_frac", 0.0)),
        )
        rules_list: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for entry in raw.get("rules", []):
            if not isinstance(entry, dict):
                continue
            if_block = entry.get("if") or {}
            then_block = entry.get("then") or {}
            rules_list.append((if_block, then_block))
        return cls(
            base_dir=base_dir,
            fallback_corner=fallback_corner,
            rules=rules_list,
            _mask_cache={},
        )

    def _load_mask_template(self, rel: str) -> np.ndarray:
        rel = rel.replace("\\", "/").lstrip("/")
        if rel in self._mask_cache:
            return self._mask_cache[rel]
        p = (self.base_dir / rel).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Mask rules: mask file not found: {p}")
        arr = np.array(Image.open(p).convert("L"))
        self._mask_cache[rel] = arr
        return arr

    def resolve(self, iw: int, ih: int) -> tuple[Optional[np.ndarray], Optional[CornerFracs]]:
        """
        Returns (mask_template_or_none, corner_or_none). Exactly one is non-None.
        mask_template is grayscale uint8; caller resizes to (iw, ih).
        """
        for if_block, then_block in self.rules:
            if not _predicates(if_block, iw, ih):
                continue
            if "mask" in then_block and then_block["mask"]:
                return self._load_mask_template(str(then_block["mask"])), None
            if all(k in then_block for k in ("w_frac", "h_frac", "margin_frac")):
                return None, _then_corner(then_block)
        return None, self.fallback_corner
