"""Result dataclasses for imaging analysis."""

from dataclasses import dataclass, field

import numpy as np

from .species import Species


@dataclass
class ODResult:
    """Result of optical depth calculation."""
    od_image: np.ndarray
    probe: np.ndarray
    reference: np.ndarray
    dark: np.ndarray | None
    roi_used: tuple[int, int, int, int] | None


@dataclass
class FitResult:
    """Result of 2D Gaussian fit to OD image."""
    atom_number: float
    center_x_px: float
    center_y_px: float
    sigma_x_px: float
    sigma_y_px: float
    sigma_x_um: float
    sigma_y_um: float
    amplitude: float
    offset: float
    fit_image: np.ndarray
    residual: np.ndarray
    success: bool
    message: str

    def summary(self) -> str:
        status = "OK" if self.success else f"FAILED ({self.message})"
        return (
            f"N = {self.atom_number:.2e}\n"
            f"Center: ({self.center_x_px:.1f}, {self.center_y_px:.1f}) px\n"
            f"Size: {self.sigma_x_um:.1f} x {self.sigma_y_um:.1f} um\n"
            f"Peak OD: {self.amplitude:.2f}\n"
            f"Fit: {status}"
        )


@dataclass
class ShotResult:
    """Combined result for one absorption image set."""
    od: ODResult
    fit: FitResult
    species: Species
    effective_pixel_um: float
    timestamp: float


@dataclass
class ToFPoint:
    """One data point in a time-of-flight series."""
    tof_ms: float
    sigma_x_um: float
    sigma_y_um: float
    atom_number: float


@dataclass
class ToFResult:
    """Temperature from time-of-flight expansion."""
    temperature_x_uK: float
    temperature_y_uK: float
    temperature_avg_uK: float
    initial_size_x_um: float
    initial_size_y_um: float
    fit_slope_x: float
    fit_slope_y: float
    r_squared_x: float
    r_squared_y: float
    points: list[ToFPoint]
    species: Species

    def summary(self) -> str:
        return (
            f"T_x = {self.temperature_x_uK:.1f} uK\n"
            f"T_y = {self.temperature_y_uK:.1f} uK\n"
            f"T_avg = {self.temperature_avg_uK:.1f} uK\n"
            f"Initial size: {self.initial_size_x_um:.1f} x {self.initial_size_y_um:.1f} um\n"
            f"R^2: x={self.r_squared_x:.4f}, y={self.r_squared_y:.4f}\n"
            f"Points: {len(self.points)}"
        )
