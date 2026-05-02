"""Absorption imaging analysis for cold atom experiments."""

__version__ = "0.1.0"

from .species import Species, SPECIES_PRESETS, get_species, list_species
from .config import CameraConfig, ImagingConfig, WatcherConfig
from .datatypes import ODResult, FitResult, ShotResult, ToFPoint, ToFResult
from .pipeline import compute_od, fit_gaussian_2d, process_shot
from .tof import measure_temperature, process_tof_series
from .io import load_image, load_image_set
from .export import save_csv, save_hdf5, save_tof_csv
