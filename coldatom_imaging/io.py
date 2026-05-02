"""Image file loading for various formats."""

from pathlib import Path

import numpy as np
from PIL import Image


def load_image(path: str | Path) -> np.ndarray:
    """Load an image file as a 2D float64 numpy array.

    Supports: bmp, png, tiff/tif, fits/fit (requires astropy).
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in (".fits", ".fit"):
        try:
            from astropy.io import fits
        except ImportError:
            raise ImportError(
                "astropy is required for FITS files. "
                "Install with: pip install coldatom-imaging[fits]"
            )
        with fits.open(path) as hdul:
            data = hdul[0].data
            if data is None:
                raise ValueError(f"No image data in {path}")
            return data.astype(np.float64)

    # PIL handles bmp, png, tiff, etc.
    img = Image.open(path)
    arr = np.array(img, dtype=np.float64)

    # Convert RGB to grayscale if needed
    if arr.ndim == 3:
        arr = np.mean(arr, axis=2)

    return arr


def load_image_set(
    probe_path: str | Path,
    reference_path: str | Path,
    dark_path: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Load a set of absorption images."""
    probe = load_image(probe_path)
    reference = load_image(reference_path)
    dark = load_image(dark_path) if dark_path else None
    return probe, reference, dark
