"""Configuration dataclasses for imaging analysis."""

from dataclasses import dataclass, field


@dataclass
class CameraConfig:
    pixel_size_um: float = 6.45       # Physical pixel size on sensor
    magnification: float = 1.0         # Imaging system magnification
    bit_depth: int = 16

    @property
    def effective_pixel_um(self) -> float:
        """Pixel size at the atoms (after magnification)."""
        return self.pixel_size_um / self.magnification

    @property
    def effective_pixel_m(self) -> float:
        return self.effective_pixel_um * 1e-6


@dataclass
class ImagingConfig:
    species: str = "Sr"
    camera: CameraConfig = field(default_factory=CameraConfig)
    roi: tuple[int, int, int, int] | None = None   # (x0, y0, x1, y1)
    od_clamp: float = 4.0
    subtract_dark: bool = True


@dataclass
class WatcherConfig:
    watch_dir: str = "."
    pattern: str = "*.tiff"
    group_size: int = 3
    poll_interval_s: float = 1.0
