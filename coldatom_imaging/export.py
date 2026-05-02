"""Export results to CSV and HDF5."""

import csv
import time
from pathlib import Path
from typing import Optional

from .datatypes import ShotResult, ToFResult


def save_csv(results: list[ShotResult], path: str, append: bool = True) -> None:
    """Save shot results to CSV. Appends by default."""
    path = Path(path)
    is_new = not path.exists() or not append

    fieldnames = [
        "timestamp", "species", "atom_number",
        "center_x_px", "center_y_px",
        "sigma_x_um", "sigma_y_um",
        "peak_od", "offset", "fit_ok",
    ]

    mode = "w" if is_new else "a"
    with open(path, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        for r in results:
            writer.writerow({
                "timestamp": r.timestamp,
                "species": r.species.symbol,
                "atom_number": f"{r.fit.atom_number:.4e}",
                "center_x_px": f"{r.fit.center_x_px:.1f}",
                "center_y_px": f"{r.fit.center_y_px:.1f}",
                "sigma_x_um": f"{r.fit.sigma_x_um:.1f}",
                "sigma_y_um": f"{r.fit.sigma_y_um:.1f}",
                "peak_od": f"{r.fit.amplitude:.3f}",
                "offset": f"{r.fit.offset:.4f}",
                "fit_ok": r.fit.success,
            })


def save_tof_csv(result: ToFResult, path: str) -> None:
    """Save ToF result to CSV."""
    path = Path(path)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["# ToF Temperature Measurement"])
        writer.writerow([f"# Species: {result.species.name}"])
        writer.writerow([f"# T_x = {result.temperature_x_uK:.1f} uK"])
        writer.writerow([f"# T_y = {result.temperature_y_uK:.1f} uK"])
        writer.writerow([f"# T_avg = {result.temperature_avg_uK:.1f} uK"])
        writer.writerow([])
        writer.writerow(["tof_ms", "sigma_x_um", "sigma_y_um", "atom_number"])
        for p in result.points:
            writer.writerow([
                f"{p.tof_ms:.2f}",
                f"{p.sigma_x_um:.1f}",
                f"{p.sigma_y_um:.1f}",
                f"{p.atom_number:.4e}",
            ])


def save_hdf5(results: list[ShotResult], path: str) -> None:
    """Save shot results with full image data to HDF5."""
    try:
        import h5py
    except ImportError:
        raise ImportError(
            "h5py is required for HDF5 export. "
            "Install with: pip install coldatom-imaging[hdf5]"
        )

    with h5py.File(path, "a") as f:
        for r in results:
            name = f"shot_{r.timestamp:.0f}"
            if name in f:
                continue
            grp = f.create_group(name)
            grp.create_dataset("od_image", data=r.od.od_image, compression="gzip")
            grp.create_dataset("fit_image", data=r.fit.fit_image, compression="gzip")
            grp.create_dataset("residual", data=r.fit.residual, compression="gzip")
            grp.attrs["species"] = r.species.symbol
            grp.attrs["atom_number"] = r.fit.atom_number
            grp.attrs["center_x_px"] = r.fit.center_x_px
            grp.attrs["center_y_px"] = r.fit.center_y_px
            grp.attrs["sigma_x_um"] = r.fit.sigma_x_um
            grp.attrs["sigma_y_um"] = r.fit.sigma_y_um
            grp.attrs["amplitude"] = r.fit.amplitude
            grp.attrs["effective_pixel_um"] = r.effective_pixel_um
            grp.attrs["fit_success"] = r.fit.success
