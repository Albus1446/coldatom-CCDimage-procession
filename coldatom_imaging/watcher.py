"""Folder watching for automatic image processing."""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from .io import load_image_set
from .config import ImagingConfig, WatcherConfig
from .pipeline import process_shot
from .datatypes import ShotResult

logger = logging.getLogger(__name__)


def _detect_roles(paths: list[Path]) -> tuple[Path, Path, Path | None]:
    """Assign probe/reference/dark roles based on filenames or order.

    If filenames contain 'probe'/'ref'/'dark', use those.
    Otherwise assume chronological: probe (1st), reference (2nd), dark (3rd).
    """
    names = {p: p.stem.lower() for p in paths}

    probe = ref = dark = None
    for p, n in names.items():
        if "probe" in n or "atom" in n or n.endswith("_1") or n.endswith("-1"):
            probe = p
        elif "ref" in n or "bright" in n or n.endswith("_2") or n.endswith("-2"):
            ref = p
        elif "dark" in n or "bg" in n or "background" in n or n.endswith("_3") or n.endswith("-3"):
            dark = p

    # Fallback: sort by modification time
    if probe is None or ref is None:
        sorted_paths = sorted(paths, key=lambda p: p.stat().st_mtime)
        probe = sorted_paths[0]
        ref = sorted_paths[1]
        dark = sorted_paths[2] if len(sorted_paths) >= 3 else None

    return probe, ref, dark


def watch_and_process(
    config: ImagingConfig,
    watcher_config: WatcherConfig,
    callback: Optional[Callable[[ShotResult], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None,
) -> None:
    """Watch a directory and process images as they appear.

    Simple polling-based watcher (no watchdog dependency required).
    Groups files by timestamp proximity or naming pattern.
    """
    watch_dir = Path(watcher_config.watch_dir)
    if not watch_dir.is_dir():
        raise FileNotFoundError(f"Watch directory not found: {watch_dir}")

    seen: set[str] = set()
    group_size = watcher_config.group_size

    logger.info("Watching %s for %s (group size: %d)",
                watch_dir, watcher_config.pattern, group_size)

    while True:
        if stop_check and stop_check():
            break

        # Find new files
        all_files = sorted(
            watch_dir.glob(watcher_config.pattern),
            key=lambda p: p.stat().st_mtime,
        )
        new_files = [f for f in all_files if str(f) not in seen]

        if len(new_files) >= group_size:
            # Take the oldest group
            group = new_files[:group_size]
            for f in group:
                seen.add(str(f))

            try:
                probe_path, ref_path, dark_path = _detect_roles(group)
                probe, ref, dark = load_image_set(probe_path, ref_path, dark_path)
                result = process_shot(probe, ref, dark, config)

                logger.info(
                    "Processed: %s -> N=%.2e, size=%.1fx%.1f um",
                    probe_path.name,
                    result.fit.atom_number,
                    result.fit.sigma_x_um,
                    result.fit.sigma_y_um,
                )

                if callback:
                    callback(result)
                else:
                    print(result.fit.summary())
                    print()

            except Exception as e:
                logger.error("Failed to process %s: %s",
                             [f.name for f in group], e)

        time.sleep(watcher_config.poll_interval_s)
