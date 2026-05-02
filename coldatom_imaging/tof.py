"""Time-of-flight temperature measurement."""

import logging

import numpy as np

from .species import Species, get_species
from .config import ImagingConfig
from .datatypes import ToFPoint, ToFResult, ShotResult
from .pipeline import process_shot

logger = logging.getLogger(__name__)

K_B = 1.380649e-23  # Boltzmann constant (J/K)


def measure_temperature(
    points: list[ToFPoint],
    species: Species,
) -> ToFResult:
    """Compute temperature from time-of-flight cloud sizes.

    Physics: sigma(t)^2 = sigma_0^2 + (k_B * T / m) * t^2
    Linear fit of sigma^2 vs t^2 gives slope = k_B * T / m.
    """
    if len(points) < 3:
        raise ValueError(f"Need at least 3 ToF points, got {len(points)}")

    t_s = np.array([p.tof_ms * 1e-3 for p in points])
    sx_m = np.array([p.sigma_x_um * 1e-6 for p in points])
    sy_m = np.array([p.sigma_y_um * 1e-6 for p in points])

    t2 = t_s ** 2
    sx2 = sx_m ** 2
    sy2 = sy_m ** 2

    # Linear fit: sigma^2 = intercept + slope * t^2
    coeffs_x = np.polyfit(t2, sx2, 1)
    coeffs_y = np.polyfit(t2, sy2, 1)

    slope_x, intercept_x = coeffs_x
    slope_y, intercept_y = coeffs_y

    # T = slope * m / k_B
    m = species.mass_kg
    T_x = slope_x * m / K_B
    T_y = slope_y * m / K_B
    T_avg = (T_x + T_y) / 2.0

    # R-squared
    def r_squared(y, y_fit):
        ss_res = np.sum((y - y_fit) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    r2_x = r_squared(sx2, np.polyval(coeffs_x, t2))
    r2_y = r_squared(sy2, np.polyval(coeffs_y, t2))

    # Initial size from intercept
    sigma0_x = np.sqrt(max(intercept_x, 0)) * 1e6  # back to um
    sigma0_y = np.sqrt(max(intercept_y, 0)) * 1e6

    logger.info(
        "ToF: T_x=%.1f uK, T_y=%.1f uK, T_avg=%.1f uK (R2: %.4f, %.4f)",
        T_x * 1e6, T_y * 1e6, T_avg * 1e6, r2_x, r2_y,
    )

    return ToFResult(
        temperature_x_uK=T_x * 1e6,
        temperature_y_uK=T_y * 1e6,
        temperature_avg_uK=T_avg * 1e6,
        initial_size_x_um=sigma0_x,
        initial_size_y_um=sigma0_y,
        fit_slope_x=slope_x,
        fit_slope_y=slope_y,
        r_squared_x=r2_x,
        r_squared_y=r2_y,
        points=points,
        species=species,
    )


def process_tof_series(
    image_sets: list[tuple[np.ndarray, np.ndarray, np.ndarray | None]],
    tof_times_ms: list[float],
    config: ImagingConfig,
) -> ToFResult:
    """Process a series of absorption images at different ToF times.

    Args:
        image_sets: List of (probe, reference, dark) tuples.
        tof_times_ms: Corresponding expansion times in ms.
        config: Imaging configuration.

    Returns:
        ToFResult with temperature and fit quality.
    """
    if len(image_sets) != len(tof_times_ms):
        raise ValueError("Number of image sets must match number of ToF times")

    points: list[ToFPoint] = []

    for (probe, ref, dark), t_ms in zip(image_sets, tof_times_ms):
        result = process_shot(probe, ref, dark, config)
        points.append(ToFPoint(
            tof_ms=t_ms,
            sigma_x_um=result.fit.sigma_x_um,
            sigma_y_um=result.fit.sigma_y_um,
            atom_number=result.fit.atom_number,
        ))
        logger.info(
            "ToF t=%.1f ms: size=%.1f x %.1f um, N=%.2e",
            t_ms, result.fit.sigma_x_um, result.fit.sigma_y_um,
            result.fit.atom_number,
        )

    species = get_species(config.species)
    return measure_temperature(points, species)
