"""Flat-field correction importer.

Delegates to :mod:`irsol_data_pipeline.io.fits_flatfield.importer`.
"""

from __future__ import annotations

from irsol_data_pipeline.io.fits_flatfield.importer import load_correction_data

__all__ = ["load_correction_data"]
