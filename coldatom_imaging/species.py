"""Atomic species presets and scattering cross-section calculation."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Species:
    """Atomic species with transition data for absorption imaging."""
    name: str
    symbol: str
    wavelength_nm: float      # Primary cooling transition
    mass_amu: float
    linewidth_MHz: float      # Natural linewidth

    @property
    def wavelength_m(self) -> float:
        return self.wavelength_nm * 1e-9

    @property
    def sigma0(self) -> float:
        """Resonant scattering cross-section: sigma = 3 * lambda^2 / (2 * pi)."""
        lam = self.wavelength_m
        return 3.0 * lam**2 / (2.0 * np.pi)

    @property
    def mass_kg(self) -> float:
        return self.mass_amu * 1.66053906660e-27


# Built-in species presets
SPECIES_PRESETS: dict[str, Species] = {
    "Sr88": Species("Strontium-88", "Sr88", 460.862, 87.906, 30.5),
    "Sr87": Species("Strontium-87", "Sr87", 460.862, 86.909, 30.5),
    "Rb87": Species("Rubidium-87", "Rb87", 780.241, 86.909, 6.07),
    "Rb85": Species("Rubidium-85", "Rb85", 780.241, 84.912, 6.07),
    "Cs":   Species("Cesium-133", "Cs", 852.347, 132.905, 5.22),
    "Yb174": Species("Ytterbium-174", "Yb174", 398.911, 173.939, 29.1),
    "Yb171": Species("Ytterbium-171", "Yb171", 398.911, 170.936, 29.1),
    "Ca40": Species("Calcium-40", "Ca40", 422.673, 39.963, 34.6),
    "Dy164": Species("Dysprosium-164", "Dy164", 421.172, 163.929, 32.2),
    "Li6":  Species("Lithium-6", "Li6", 670.977, 6.015, 5.87),
    "Li7":  Species("Lithium-7", "Li7", 670.977, 7.016, 5.87),
    "Na":   Species("Sodium-23", "Na", 589.158, 22.990, 9.80),
    "K40":  Species("Potassium-40", "K40", 766.701, 39.964, 6.04),
    "K39":  Species("Potassium-39", "K39", 766.701, 38.964, 6.04),
    "Er":   Species("Erbium-168", "Er", 400.910, 167.932, 29.7),
}

# Convenience aliases
SPECIES_PRESETS["Sr"] = SPECIES_PRESETS["Sr88"]
SPECIES_PRESETS["Rb"] = SPECIES_PRESETS["Rb87"]
SPECIES_PRESETS["Yb"] = SPECIES_PRESETS["Yb174"]
SPECIES_PRESETS["Ca"] = SPECIES_PRESETS["Ca40"]
SPECIES_PRESETS["Dy"] = SPECIES_PRESETS["Dy164"]
SPECIES_PRESETS["Li"] = SPECIES_PRESETS["Li6"]
SPECIES_PRESETS["K"] = SPECIES_PRESETS["K40"]


def get_species(name: str) -> Species:
    """Get a species by name. Raises KeyError if not found."""
    if name in SPECIES_PRESETS:
        return SPECIES_PRESETS[name]
    raise KeyError(
        f"Unknown species '{name}'. Available: {', '.join(sorted(SPECIES_PRESETS.keys()))}"
    )


def list_species() -> str:
    """Print a table of all available species."""
    lines = [
        f"{'Symbol':<8} {'Name':<20} {'λ (nm)':<10} {'σ₀ (m²)':<14} {'Mass (amu)':<12} {'Γ (MHz)':<10}",
        "-" * 74,
    ]
    seen = set()
    for key, sp in sorted(SPECIES_PRESETS.items()):
        if sp.name in seen:
            continue
        seen.add(sp.name)
        lines.append(
            f"{sp.symbol:<8} {sp.name:<20} {sp.wavelength_nm:<10.3f} "
            f"{sp.sigma0:<14.4e} {sp.mass_amu:<12.3f} {sp.linewidth_MHz:<10.2f}"
        )
    return "\n".join(lines)
