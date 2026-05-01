"""
Recursive batch inpaint: mirror folder layout and filenames under --output.
Loads LaMa (or chosen model) once per process; same mask resized per image.
Use --workers > 1 for parallel processes (each loads the model; higher RAM).
"""
from __future__ import annotations

import argparse
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

from iopaint.helper import pil_to_bytes
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


def _short_rel(rel: Path, max_len: int = 52) -> str:
    s = rel.as_posix()
    if len(s) <= max_len:
        return s
    return "…" + s[-(max_len - 1) :]


def inpaint_one(
    root_in: Path,
    root_out: Path,
    image_p: Path,
    base_mask: np.ndarray,
    model_manager: ModelManager,
    inpaint_request: InpaintRequest,
    quality: int,
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

    mask_img = base_mask.copy()
    if mask_img.shape[:2] != img.shape[:2]:
        mask_img = cv2.resize(
            mask_img,
            (img.shape[1], img.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )
    mask_img[mask_img >= 127] = 255
    mask_img[mask_img < 127] = 0

    inpaint_bgr = model_manager(img, mask_img, inpaint_request)
    inpaint_rgb = cv2.cvtColor(inpaint_bgr, cv2.COLOR_BGR2RGB)

    save_image(inpaint_rgb, out_p, infos, quality)
    torch_gc()
    return rel


def _mp_init(mask_path: str, model_name: str, device: str, req_dict: dict, quality: int) -> None:
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
    _MP["base_mask"] = np.array(Image.open(mask_path).convert("L"))


def _mp_run(task: tuple[str, str, str]) -> str:
    root_in_s, root_out_s, image_s = task
    rel = inpaint_one(
        Path(root_in_s),
        Path(root_out_s),
        Path(image_s),
        _MP["base_mask"],
        _MP["model"],
        _MP["req"],
        _MP["quality"],
    )
    return rel.as_posix()


def main() -> None:
    console = Console(highlight=False)
    t0 = time.monotonic()

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True, help="Root folder (recursive)")
    ap.add_argument("--output", type=Path, required=True, help="Root folder; mirrors --input layout")
    ap.add_argument("--mask", type=Path, required=True, help="Single mask PNG (white = inpaint)")
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
    if not mask_path.is_file():
        console.print(Panel("[bold red]Mask file is missing.[/]", border_style="red"))
        raise SystemExit(1)

    images = iter_images(root_in)
    if not images:
        console.print(Panel("[bold red]No supported images found under the input folder.[/]", border_style="red"))
        raise SystemExit(1)

    n_cpu = os.cpu_count() or 8
    requested = max(1, args.workers)
    effective_workers = max(1, min(requested, len(images), n_cpu))
    if effective_workers != requested:
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

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="dim", justify="right")
    summary.add_column(style="default")
    summary.add_row("Images queued", f"[bold]{len(images)}[/]")
    summary.add_row("Model", f"[cyan]{args.model}[/]")
    summary.add_row("HD strategy", "[green]Original[/]  (no resize / crop tiling)")
    summary.add_row("Output layout", "[white]Mirrors input folders and filenames[/]")
    summary.add_row(
        "Parallel workers",
        f"[bold]{effective_workers}[/]  [dim](each process loads the model; ~N x RAM)[/]",
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
            base_mask = np.array(Image.open(mask_path).convert("L"))
            console.print("[green]Model ready.[/]     [dim]Processing queue...[/]\n")
            for image_p in images:
                rel = image_p.relative_to(root_in)
                progress.update(task_id, rel=_short_rel(rel), refresh=True)
                inpaint_one(
                    root_in,
                    root_out,
                    image_p,
                    base_mask,
                    model_manager,
                    inpaint_request,
                    args.quality,
                )
                progress.advance(task_id)
        else:
            console.print(
                f"[dim]Spawning {effective_workers} worker processes "
                f"(first batch may pause while models load)...[/]\n",
            )
            with ProcessPoolExecutor(
                max_workers=effective_workers,
                initializer=_mp_init,
                initargs=(str(mask_path), args.model, args.device, req_dict, args.quality),
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
