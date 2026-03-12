"""Flat-field domain models."""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict

from irsol_data_pipeline.core.metadata import MeasurementMetadata
from irsol_data_pipeline.core.types import StokesParameters


class FlatField(BaseModel):
    """A flat-field measurement loaded from a .dat file."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_path: Path
    metadata: MeasurementMetadata
    stokes: StokesParameters

    @property
    def wavelength(self) -> int:
        return self.metadata.wavelength

    @property
    def timestamp(self) -> datetime.datetime:
        return self.metadata.datetime_start


class FlatFieldCorrection(BaseModel):
    """A computed flat-field correction ready to be applied.

    This stores the analysis results (dust flat map and offset map)
    from a flat-field analysis. The offset_map type depends on the
    correction backend (e.g. spectroflat OffsetMap).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_flatfield_path: Path
    dust_flat: np.ndarray
    offset_map: object  # Backend-specific (e.g. spectroflat OffsetMap)
    desmiled: np.ndarray
    timestamp: datetime.datetime
    wavelength: int
