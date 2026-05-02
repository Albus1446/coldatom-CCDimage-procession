"""Core analysis pipeline: OD calculation, 2D Gaussian fit, atom number."""

import time
import logging
from typing import Optional

import numpy as np
from scipy.optimize import curve_fit

from .species import Species, get_species
from .config import ImagingConfig
from .datatypes import ODResult, FitResult, ShotResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OD calculation
# ---------------------------------------------------------------------------

def compute_od(
    probe: np.ndarray,
    reference: np.ndarray,
    dark: np.ndarray | None = None,
    clamp: float = 4.0,
) -> np.ndarray:
    """Compute optical depth from absorption images.

    OD(x,y) = -ln( (probe - dark) / (reference - dark) )
    """
    if dark is not None:
        probe_c = probe - dark
        ref_c = reference - dark
    else:
        probe_c = probe.copy()
        ref_c = reference.copy()

    # Avoid division by zero / log of negative
    ref_c = np.maximum(ref_c, 1.0)
    probe_c = np.maximum(probe_c, 1.0)

    ratio = probe_c / ref_c
    od = -np.log(ratio)

    # Clamp to reasonable range
    od = np.clip(od, 0.0, clamp)
    return od


# ---------------------------------------------------------------------------
# 2D Gaussian fitting
# ---------------------------------------------------------------------------

def _gaussian_2d(coords, amplitude, x0, y0, sigma_x, sigma_y, offset):
    """2D Gaussian model (no rotation)."""
    x, y = coords
    return (
        amplitude * np.exp(
            -((x - x0) ** 2 / (2 * sigma_x ** 2)
              + (y - y0) ** 2 / (2 * sigma_y ** 2))
        )
        + offset
    )


def _initial_guess(od: np.ndarray) -> tuple:
    """Estimate Gaussian parameters from image moments."""
    total = od.sum()
    if total <= 0:
        ny, nx = od.shape
        return (0.1, nx / 2, ny / 2, nx / 10, ny / 10, 0.0)

    y_idx, x_idx = np.mgrid[0:od.shape[0], 0:od.shape[1]]

    x0 = (x_idx * od).sum() / total
    y0 = (y_idx * od).sum() / total

    sx = np.sqrt((((x_idx - x0) ** 2) * od).sum() / total)
    sy = np.sqrt((((y_idx - y0) ** 2) * od).sum() / total)

    sx = max(sx, 1.0)
    sy = max(sy, 1.0)

    amplitude = od.max()
    offset = np.median(od[od < np.percentile(od, 10)]) if od.size > 10 else 0.0

    return (amplitude, x0, y0, sx, sy, offset)


def fit_gaussian_2d(
    od: np.ndarray,
    effective_pixel_um: float = 1.0,
    sigma0: float = 1.0,
) -> FitResult:
    """Fit a 2D Gaussian to an OD image.

    Returns FitResult with atom number, cloud size, fit quality.
    """
    ny, nx = od.shape
    y_idx, x_idx = np.mgrid[0:ny, 0:nx]
    coords = (x_idx.ravel(), y_idx.ravel())
    data = od.ravel()

    guess = _initial_guess(od)
    bounds_lo = [0, 0, 0, 0.5, 0.5, -1.0]
    bounds_hi = [max(guess[0] * 3, 1.0), nx, ny, nx / 2, ny / 2, max(guess[0], 1.0)]
    # Clamp guess to be within bounds
    guess = tuple(
        max(lo, min(hi, g)) for g, lo, hi in zip(guess, bounds_lo, bounds_hi)
    )

    try:
        popt, _ = curve_fit(
            _gaussian_2d,
            coords,
            data,
            p0=guess,
            bounds=(bounds_lo, bounds_hi),
            maxfev=5000,
        )
        success = True
        message = "ok"
    except (RuntimeError, ValueError) as e:
        # Fall back to moment-based estimates
        popt = np.array(guess)
        success = False
        message = str(e)

    amplitude, x0, y0, sx, sy, offset = popt

    # Atom number: N = integral(OD) / sigma0
    # For Gaussian: integral = 2*pi*A*sx*sy (in pixel units)
    pixel_area = (effective_pixel_um * 1e-6) ** 2
    atom_number = 2 * np.pi * amplitude * sx * sy * pixel_area / sigma0

    # Generate fit image
    fit_image = _gaussian_2d(
        (x_idx, y_idx), amplitude, x0, y0, sx, sy, offset
    )
    residual = od - fit_image

    return FitResult(
        atom_number=atom_number,
        center_x_px=x0,
        center_y_px=y0,
        sigma_x_px=sx,
        sigma_y_px=sy,
        sigma_x_um=sx * effective_pixel_um,
        sigma_y_um=sy * effective_pixel_um,
        amplitude=amplitude,
        offset=offset,
        fit_image=fit_image,
        residual=residual,
        success=success,
        message=message,
    )


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def process_shot(
    probe: np.ndarray,
    reference: np.ndarray,
    dark: np.ndarray | None,
    config: ImagingConfig,
) -> ShotResult:
    """Process a single absorption image set.

    probe/reference/dark -> OD -> fit -> atom number + cloud size.
    """
    species = get_species(config.species)
    pixel_um = config.camera.effective_pixel_um

    # Compute OD
    od = compute_od(
        probe, reference,
        dark if config.subtract_dark else None,
        clamp=config.od_clamp,
    )

    # Apply ROI
    roi_used = config.roi
    if config.roi:
        x0, y0, x1, y1 = config.roi
        od_roi = od[y0:y1, x0:x1]
    else:
        od_roi = od

    # Fit
    fit = fit_gaussian_2d(od_roi, pixel_um, species.sigma0)

    # Adjust center for ROI offset
    if config.roi:
        fit.center_x_px += config.roi[0]
        fit.center_y_px += config.roi[1]

    od_result = ODResult(
        od_image=od,
        probe=probe,
        reference=reference,
        dark=dark,
        roi_used=roi_used,
    )

    logger.info(
        "Shot processed: N=%.2e, size=%.1fx%.1f um, peak_OD=%.2f (%s)",
        fit.atom_number, fit.sigma_x_um, fit.sigma_y_um,
        fit.amplitude, species.symbol,
    )

    return ShotResult(
        od=od_result,
        fit=fit,
        species=species,
        effective_pixel_um=pixel_um,
        timestamp=time.time(),
    )
