"""Measurement domain model."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from irsol_data_pipeline.core.metadata import MeasurementMetadata
from irsol_data_pipeline.core.types import StokesParameters
import datetime


class Measurement(BaseModel):
    """A solar observation measurement loaded from a .dat file."""

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

    @property
    def name(self) -> str:
        return self.source_path.stem
