"""Command-line interface for coldatom-imaging."""

import argparse
import logging
import sys

from .species import list_species, get_species
from .config import CameraConfig, ImagingConfig, WatcherConfig
from .io import load_image_set
from .pipeline import process_shot
from .tof import process_tof_series
from .export import save_csv, save_tof_csv


def cmd_analyze(args):
    config = ImagingConfig(
        species=args.species,
        camera=CameraConfig(
            pixel_size_um=args.pixel_size,
            magnification=args.magnification,
        ),
    )

    probe, ref, dark = load_image_set(args.probe, args.reference, args.dark)
    result = process_shot(probe, ref, dark, config)

    print(result.fit.summary())
    print(f"Species: {result.species.name} (sigma0={result.species.sigma0:.4e} m^2)")
    print(f"Pixel: {config.camera.effective_pixel_um:.2f} um/px")

    if args.output:
        save_csv([result], args.output)
        print(f"\nSaved to {args.output}")


def cmd_tof(args):
    config = ImagingConfig(
        species=args.species,
        camera=CameraConfig(
            pixel_size_um=args.pixel_size,
            magnification=args.magnification,
        ),
    )

    tof_times = [float(t) for t in args.tof_times.split(",")]

    from pathlib import Path
    tof_dir = Path(args.directory)
    if not tof_dir.is_dir():
        print(f"Error: {tof_dir} is not a directory")
        sys.exit(1)

    # Find image groups sorted by name
    image_files = sorted(tof_dir.glob(args.pattern))
    group_size = 3
    if len(image_files) < len(tof_times) * group_size:
        print(f"Error: expected {len(tof_times) * group_size} images "
              f"({len(tof_times)} ToF points x {group_size}), "
              f"found {len(image_files)}")
        sys.exit(1)

    image_sets = []
    for i in range(len(tof_times)):
        files = image_files[i * group_size:(i + 1) * group_size]
        probe, ref, dark = load_image_set(files[0], files[1],
                                          files[2] if len(files) > 2 else None)
        image_sets.append((probe, ref, dark))

    result = process_tof_series(image_sets, tof_times, config)
    print(result.summary())

    if args.output:
        save_tof_csv(result, args.output)
        print(f"\nSaved to {args.output}")


def cmd_watch(args):
    config = ImagingConfig(
        species=args.species,
        camera=CameraConfig(
            pixel_size_um=args.pixel_size,
            magnification=args.magnification,
        ),
    )
    watcher_config = WatcherConfig(
        watch_dir=args.directory,
        pattern=args.pattern,
    )

    from .watcher import watch_and_process

    results = []

    def on_result(result):
        print(result.fit.summary())
        print()
        results.append(result)
        if args.output:
            save_csv([result], args.output, append=True)

    print(f"Watching {args.directory} for {args.pattern}...")
    print("Press Ctrl+C to stop.\n")

    try:
        watch_and_process(config, watcher_config, callback=on_result)
    except KeyboardInterrupt:
        print(f"\nStopped. Processed {len(results)} shots.")


def cmd_list_species(args):
    print(list_species())


def cmd_gui(args):
    try:
        from .gui import run_gui
        run_gui()
    except ImportError as e:
        print(f"GUI requires PyQt5 and matplotlib: {e}")
        print("Install with: pip install coldatom-imaging[gui]")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="coldatom-imaging",
        description="Absorption imaging analysis for cold atom experiments",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze a single shot")
    p_analyze.add_argument("probe", help="Probe image path")
    p_analyze.add_argument("reference", help="Reference image path")
    p_analyze.add_argument("dark", nargs="?", default=None, help="Dark image path")
    p_analyze.add_argument("-s", "--species", default="Sr")
    p_analyze.add_argument("-p", "--pixel-size", type=float, default=6.45)
    p_analyze.add_argument("-m", "--magnification", type=float, default=1.0)
    p_analyze.add_argument("-o", "--output", help="CSV output path")
    p_analyze.set_defaults(func=cmd_analyze)

    # tof
    p_tof = sub.add_parser("tof", help="Time-of-flight temperature measurement")
    p_tof.add_argument("directory", help="Directory with ToF image series")
    p_tof.add_argument("-t", "--tof-times", required=True,
                       help="Comma-separated ToF times in ms (e.g., 1,2,5,10,15)")
    p_tof.add_argument("-s", "--species", default="Sr")
    p_tof.add_argument("-p", "--pixel-size", type=float, default=6.45)
    p_tof.add_argument("-m", "--magnification", type=float, default=1.0)
    p_tof.add_argument("--pattern", default="*.tiff")
    p_tof.add_argument("-o", "--output", help="CSV output path")
    p_tof.set_defaults(func=cmd_tof)

    # watch
    p_watch = sub.add_parser("watch", help="Watch folder for new images")
    p_watch.add_argument("directory", help="Directory to watch")
    p_watch.add_argument("-s", "--species", default="Sr")
    p_watch.add_argument("-p", "--pixel-size", type=float, default=6.45)
    p_watch.add_argument("-m", "--magnification", type=float, default=1.0)
    p_watch.add_argument("--pattern", default="*.tiff")
    p_watch.add_argument("-o", "--output", help="CSV output path (append mode)")
    p_watch.set_defaults(func=cmd_watch)

    # list-species
    p_list = sub.add_parser("list-species", help="Show available species presets")
    p_list.set_defaults(func=cmd_list_species)

    # gui
    p_gui = sub.add_parser("gui", help="Launch GUI")
    p_gui.set_defaults(func=cmd_gui)

    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
