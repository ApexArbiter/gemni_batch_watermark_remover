"""
Recursive batch inpaint: mirror folder layout and filenames under --output.
Loads LaMa (or chosen model) once per process.

Masks: single PNG (--mask), uniform corner fractions (--use-corner-mask), or
per-image rules from JSON (--mask-rules) for mixed sizes / different placements.
Use --workers > 1 for parallel processes (each loads the model; higher RAM).
"""
from __future__ import annotations

import argparse
from typing import Optional, Tuple
import json
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF")
warnings.filterwarnings("ignore", category=FutureWarning)

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="ERROR", format="{message}")

import cv2
import numpy as np
from PIL import Image, ImageOps
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.rule import Rule
from rich.status import Status
from rich.table import Table

from iopaint.download import cli_download_model, scan_models
from iopaint.helper import pil_to_bytes

from make_corner_mask import build_corner_mask_array
from mask_rules import MaskRules
from iopaint.model.utils import torch_gc
from iopaint.model_manager import ModelManager
from iopaint.schema import HDStrategy, InpaintRequest

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}

# Populated in child processes only (multiprocessing).
_MP: dict = {}


def iter_images(root: Path) -> list[Path]:
    root = root.resolve()
    out: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES:
            out.append(p.resolve())
    return out


def save_image(arr_rgb: np.ndarray, dest: Path, infos: dict, quality: int) -> None:
    ext = dest.suffix.lower().lstrip(".") or "png"
    if ext == "jpg":
        ext = "jpeg"
    pil = Image.fromarray(arr_rgb)
    data = pil_to_bytes(pil, ext, quality=quality, infos=infos)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def ensure_erase_model_downloaded(model_name: str, console: Console) -> None:
    """IOPaint only lists erase models after weights exist; official CLI downloads first."""
    if model_name in [it.name for it in scan_models()]:
        return
    console.print(
        f"[yellow]First run:[/] downloading [bold]{model_name}[/] weights (~200 MB). "
        "[dim]Internet required; files are cached for later runs.[/]"
    )
    with console.status(
        f"[bold cyan]Downloading {model_name}...[/]",
        spinner="dots12",
        spinner_style="cyan",
    ):
        cli_download_model(model_name)


def _short_rel(rel: Path, max_len: int = 52) -> str:
    s = rel.as_posix()
    if len(s) <= max_len:
        return s
    return "…" + s[-(max_len - 1) :]


CornerFracs = Tuple[float, float, float, float]


def inpaint_one(
    root_in: Path,
    root_out: Path,
    image_p: Path,
    base_mask: Optional[np.ndarray],
    corner_fracs: Optional[CornerFracs],
    model_manager: ModelManager,
    inpaint_request: InpaintRequest,
    quality: int,
    mask_rules: Optional[MaskRules] = None,
) -> Path:
    rel = image_p.relative_to(root_in)
    out_p = root_out / rel

    infos = Image.open(image_p).info
    im = Image.open(image_p)
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    im = im.convert("RGB")
    img = np.array(im)
    ih, iw = img.shape[:2]

    if mask_rules is not None:
        tmpl, cr = mask_rules.resolve(iw, ih)
        if tmpl is not None:
            mask_img = tmpl.copy()
            if mask_img.shape[:2] != (ih, iw):
                mask_img = cv2.resize(
                    mask_img,
                    (iw, ih),
                    interpolation=cv2.INTER_NEAREST,
                )
        else:
            assert cr is not None
            wf, hf, mf, pf = cr
            mask_img = build_corner_mask_array(iw, ih, wf, hf, mf, pf)
    elif corner_fracs is not None:
        wf, hf, mf, pf = corner_fracs
        mask_img = build_corner_mask_array(iw, ih, wf, hf, mf, pf)
    else:
        assert base_mask is not None
        mask_img = base_mask.copy()
        if mask_img.shape[:2] != (ih, iw):
            mask_img = cv2.resize(
                mask_img,
                (iw, ih),
                interpolation=cv2.INTER_NEAREST,
            )
    mask_img[mask_img >= 127] = 255
    mask_img[mask_img < 127] = 0

    inpaint_bgr = model_manager(img, mask_img, inpaint_request)
    inpaint_rgb = cv2.cvtColor(inpaint_bgr, cv2.COLOR_BGR2RGB)

    save_image(inpaint_rgb, out_p, infos, quality)
    torch_gc()
    return rel


def _mp_init(
    mask_path: str,
    use_corner_mask: bool,
    corner_wf: float,
    corner_hf: float,
    corner_mf: float,
    corner_pf: float,
    model_name: str,
    device: str,
    req_dict: dict,
    quality: int,
    rules_path: str,
) -> None:
    import torch

    try:
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
    except Exception:
        pass
    global _MP
    _MP["model"] = ModelManager(name=model_name, device=device)
    _MP["req"] = InpaintRequest(**req_dict)
    _MP["quality"] = quality
    _MP["mask_rules"] = MaskRules.load(Path(rules_path)) if rules_path else None
    _MP["use_corner"] = use_corner_mask
    if _MP["mask_rules"] is not None:
        _MP["corner"] = None
        _MP["base_mask"] = None
    elif use_corner_mask:
        _MP["corner"] = (corner_wf, corner_hf, corner_mf, corner_pf)
        _MP["base_mask"] = None
    else:
        _MP["corner"] = None
        _MP["base_mask"] = np.array(Image.open(mask_path).convert("L"))


def _mp_run(task: tuple[str, str, str]) -> str:
    root_in_s, root_out_s, image_s = task
    rel = inpaint_one(
        Path(root_in_s),
        Path(root_out_s),
        Path(image_s),
        _MP["base_mask"],
        _MP["corner"],
        _MP["model"],
        _MP["req"],
        _MP["quality"],
        _MP.get("mask_rules"),
    )
    return rel.as_posix()


def main() -> None:
    console = Console(highlight=False)
    t0 = time.monotonic()

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True, help="Root folder (recursive)")
    ap.add_argument("--output", type=Path, required=True, help="Root folder; mirrors --input layout")
    ap.add_argument(
        "--mask",
        type=Path,
        default=None,
        help="PNG mask (white = inpaint). Not needed if --use-corner-mask.",
    )
    ap.add_argument(
        "--use-corner-mask",
        action="store_true",
        help="Build bottom-right rectangle per image from fractions (fixes mixed resolutions/aspects).",
    )
    ap.add_argument("--corner-w-frac", type=float, default=0.12)
    ap.add_argument("--corner-h-frac", type=float, default=0.20)
    ap.add_argument("--corner-margin-frac", type=float, default=0.08)
    ap.add_argument("--corner-pad-frac", type=float, default=0.0)
    ap.add_argument(
        "--mask-rules",
        type=Path,
        default=None,
        help="JSON: per-image corner fractions or mask PNG by width/height predicates (see mask-rules.example.json).",
    )
    ap.add_argument("--model", default="lama")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"])
    ap.add_argument("--config", type=Path, default=None, help="Optional InpaintRequest JSON")
    ap.add_argument("--quality", type=int, default=95, help="JPEG/WebP quality (PNG ignores)")
    ap.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel processes. Each loads its own model (more RAM). 1 = sequential. Suggest <= logical CPUs.",
    )
    args = ap.parse_args()

    root_in = args.input.resolve()
    root_out = args.output.resolve()

    mask_rules_obj: Optional[MaskRules] = None
    if args.mask_rules is not None:
        if not args.mask_rules.is_file():
            console.print(
                Panel(f"[bold red]--mask-rules not found:[/] {args.mask_rules}", border_style="red"),
            )
            raise SystemExit(1)
        mask_rules_obj = MaskRules.load(args.mask_rules.resolve())
        mask_path: Optional[Path] = None
        corner_tuple: Optional[CornerFracs] = None
    elif args.use_corner_mask:
        mask_path = None
        corner_tuple = (
            args.corner_w_frac,
            args.corner_h_frac,
            args.corner_margin_frac,
            args.corner_pad_frac,
        )
    else:
        corner_tuple = None
        if args.mask is None or not args.mask.is_file():
            console.print(
                Panel(
                    "[bold red]Missing --mask PNG[/], or use [bold]--use-corner-mask[/], "
                    "or [bold]--mask-rules[/] JSON. Run scan_image_sizes.py on your folder first.",
                    border_style="red",
                ),
            )
            raise SystemExit(1)
        mask_path = args.mask.resolve()

    console.print()
    console.print(
        Rule("[bold white]Watermark removal  |  batch job[/]", style="bright_blue"),
        style=None,
    )
    console.print(
        f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/]     "
        "[bold]IOPaint / LaMa[/]     [dim]full-resolution mode[/]",
        justify="center",
    )
    console.print()

    if not root_in.is_dir():
        console.print(Panel("[bold red]Input folder is missing or not a directory.[/]", border_style="red"))
        raise SystemExit(1)
    if mask_path is not None and not mask_path.is_file():
        console.print(Panel("[bold red]Mask file is missing.[/]", border_style="red"))
        raise SystemExit(1)

    if mask_rules_obj is not None and args.mask is not None:
        console.print(
            "[dim]Note:[/] [bold]--mask-rules[/] is active; single-file [bold]--mask[/] is ignored.",
        )
        console.print()

    images = iter_images(root_in)
    if not images:
        console.print(Panel("[bold red]No supported images found under the input folder.[/]", border_style="red"))
        raise SystemExit(1)

    n_cpu = os.cpu_count() or 8
    requested = max(1, args.workers)
    effective_workers = max(1, min(requested, len(images), n_cpu))

    # One GPU cannot host N independent LaMa copies (each worker loads full weights to CUDA).
    # Parallel GPU workers → VRAM OOM almost immediately on 8 GB cards.
    using_cuda = str(args.device).lower() == "cuda"
    if using_cuda and effective_workers > 1:
        console.print(
            Panel(
                f"You asked for [bold]{effective_workers}[/] workers with [bold]CUDA[/]. "
                "Every worker loads its own LaMa onto the same GPU, which causes "
                "[bold red]out-of-memory[/] during model load.\n\n"
                "[green]Using workers = 1[/] for GPU. "
                "(Parallel workers only make sense for CPU in this script.)",
                border_style="yellow",
                title="GPU / workers",
            ),
        )
        console.print()
        effective_workers = 1

    if not using_cuda and effective_workers != requested:
        console.print(
            f"[dim]Workers: using {effective_workers} (requested {requested}, "
            f"capped by image count and CPU count {n_cpu}).[/]",
        )
        console.print()

    no_hd_resize = {
        "hd_strategy": HDStrategy.ORIGINAL,
        "use_croper": False,
        "use_extender": False,
    }
    if config_path := args.config:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        data.update(no_hd_resize)
        inpaint_request = InpaintRequest(**data)
    else:
        inpaint_request = InpaintRequest(**no_hd_resize)

    req_dict = inpaint_request.model_dump(mode="json")

    ensure_erase_model_downloaded(args.model, console)
    console.print()

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="dim", justify="right")
    summary.add_column(style="default")
    summary.add_row("Images queued", f"[bold]{len(images)}[/]")
    summary.add_row("Model", f"[cyan]{args.model}[/]")
    summary.add_row("HD strategy", "[green]Original[/]  (no resize / crop tiling)")
    if mask_rules_obj is not None:
        mask_summary = "[cyan]JSON rules[/]  [dim](corners and/or masks by size)[/]"
    elif corner_tuple:
        mask_summary = "[cyan]Per-image corner[/]  [dim](fractions)[/]"
    else:
        mask_summary = "[cyan]PNG[/] resized per photo"
    summary.add_row("Mask", mask_summary)
    summary.add_row("Output layout", "[white]Mirrors input folders and filenames[/]")
    summary.add_row(
        "Parallel workers",
        f"[bold]{effective_workers}[/]"
        + (
            "  [dim](CUDA: always 1 on a single GPU)[/]"
            if using_cuda
            else "  [dim](each process loads the model; ~N x RAM)[/]"
        ),
    )
    console.print(
        Panel(summary, title="[bold]Job summary[/]", border_style="blue", padding=(1, 2)),
    )
    console.print()

    tasks = [(str(root_in), str(root_out), str(p)) for p in images]

    progress_columns = [
        SpinnerColumn(style="cyan"),
        TextColumn("[bold]{task.fields[rel]}[/]", justify="left", markup=True),
        BarColumn(complete_style="green", finished_style="green", bar_width=36),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ]

    with Progress(
        *progress_columns,
        console=console,
        transient=False,
    ) as progress:
        task_id = progress.add_task("batch", total=len(images), rel="Starting...")

        if effective_workers == 1:
            with console.status("[bold cyan]Loading model...[/]", spinner="dots12", spinner_style="cyan"):
                model_manager = ModelManager(name=args.model, device=args.device)
            base_mask_arr: Optional[np.ndarray] = (
                None
                if (corner_tuple or mask_rules_obj)
                else np.array(Image.open(mask_path).convert("L"))
            )
            console.print("[green]Model ready.[/]     [dim]Processing queue...[/]\n")
            for image_p in images:
                rel = image_p.relative_to(root_in)
                progress.update(task_id, rel=_short_rel(rel), refresh=True)
                inpaint_one(
                    root_in,
                    root_out,
                    image_p,
                    base_mask_arr,
                    corner_tuple,
                    model_manager,
                    inpaint_request,
                    args.quality,
                    mask_rules_obj,
                )
                progress.advance(task_id)
        else:
            console.print(
                f"[dim]Spawning {effective_workers} worker processes "
                f"(first batch may pause while models load)...[/]\n",
            )
            mp_mask = "" if mask_path is None else str(mask_path)
            rules_s = str(args.mask_rules.resolve()) if args.mask_rules else ""
            with ProcessPoolExecutor(
                max_workers=effective_workers,
                initializer=_mp_init,
                initargs=(
                    mp_mask,
                    bool(corner_tuple),
                    args.corner_w_frac,
                    args.corner_h_frac,
                    args.corner_margin_frac,
                    args.corner_pad_frac,
                    args.model,
                    args.device,
                    req_dict,
                    args.quality,
                    rules_s,
                ),
            ) as pool:
                futures = {pool.submit(_mp_run, t): t for t in tasks}
                for fut in as_completed(futures):
                    task_tuple = futures[fut]
                    rel_s = fut.result()
                    progress.update(task_id, rel=_short_rel(Path(rel_s)), refresh=True)
                    progress.advance(task_id)

    elapsed = time.monotonic() - t0
    avg = elapsed / len(images) if images else 0.0

    console.print()
    console.print(Rule("[bold green]Job completed successfully[/]", style="green"))
    footer = Table.grid(padding=(0, 2))
    footer.add_column(style="dim", justify="right")
    footer.add_column(style="white")
    footer.add_row("Images processed", f"[bold green]{len(images)}[/]")
    footer.add_row("Wall time", f"{elapsed:.1f} s  [dim](avg {avg:.2f} s / image)[/]")
    footer.add_row("Workers used", f"[cyan]{effective_workers}[/]")
    footer.add_row("Status", "[bold green]All outputs written[/]")
    console.print(Panel(footer, border_style="green", padding=(1, 2)))
    console.print()


if __name__ == "__main__":
    import multiprocessing as mp

    mp.freeze_support()
    main()
