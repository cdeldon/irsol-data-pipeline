"""Wavelength calibration domain model."""

from __future__ import annotations

from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict


class CalibrationResult(BaseModel):
    """Result of wavelength auto-calibration.

    The calibration maps pixel positions to wavelengths using a linear model:
        wavelength = pixel_scale * pixel + wavelength_offset
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    pixel_scale: float  # a1: angstrom per pixel
    wavelength_offset: float  # a0: wavelength at pixel 0
    pixel_scale_error: float  # 1-sigma error on a1
    wavelength_offset_error: float  # 1-sigma error on a0
    reference_file: str  # name of reference data file used
    peak_pixels: Optional[np.ndarray] = None  # pixel positions of fitted peaks
    reference_lines: Optional[np.ndarray] = None  # wavelengths of the reference lines

    def pixel_to_wavelength(self, pixel: float) -> float:
        """Convert a pixel position to wavelength in Angstrom."""
        return self.pixel_scale * pixel + self.wavelength_offset

    def wavelength_to_pixel(self, wavelength: float) -> float:
        """Convert a wavelength in Angstrom to pixel position."""
        return (wavelength - self.wavelength_offset) / self.pixel_scale
