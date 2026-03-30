"""Flat-field correction exporter.

Delegates to :mod:`irsol_data_pipeline.io.fits_flatfield.exporter`.
"""

from __future__ import annotations

from irsol_data_pipeline.io.fits_flatfield.exporter import write_correction_data

__all__ = ["write_correction_data"]
