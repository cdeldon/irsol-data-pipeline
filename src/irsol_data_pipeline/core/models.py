"""Domain model."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from irsol_data_pipeline.core.config import DEFAULT_MAX_DELTA


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

    This stores the analysis results (dust flat map and offset map) from
    a flat-field analysis. The offset_map type depends on the correction
    backend (e.g. spectroflat OffsetMap).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_flatfield_path: Path
    dust_flat: np.ndarray
    offset_map: object  # Backend-specific (e.g. spectroflat OffsetMap)
    desmiled: np.ndarray
    timestamp: datetime.datetime
    wavelength: int


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


class MeasurementMetadata(BaseModel):
    """Decoded metadata extracted from a ZIMPOL .dat info array.

    All fields are extracted once at construction time so that
    downstream code never touches the raw byte array.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    wavelength: int
    datetime_start: datetime.datetime
    datetime_end: Optional[datetime.datetime]
    telescope_name: str
    instrument: str
    measurement_name: str
    measurement_type: str
    measurement_id: str
    observer: str
    project: str
    camera_identity: str
    camera_ccd: str
    camera_temperature: Optional[float]
    integration_time: Optional[float]
    images: str
    solar_p0: Optional[float]
    solar_disc_coordinates: Optional[str]
    derotator_position_angle: Optional[float]
    derotator_offset: Optional[float]
    derotator_coordinate_system: Optional[str]
    spectrograph_slit: Optional[str]
    reduction_outfname: Optional[str]

    # Keep the raw decoded dict for any field we haven't explicitly modeled.
    _raw: dict[str, str] = PrivateAttr(default_factory=dict)

    @staticmethod
    def from_info_array(info: np.ndarray) -> "MeasurementMetadata":
        """Build metadata from a ZIMPOL info Nx2 byte array."""
        raw = _decode_info(info)

        def _get(key: str) -> Optional[str]:
            return raw.get(key)

        def _get_required(key: str) -> str:
            v = raw.get(key)
            if v is None:
                raise KeyError(f"Required metadata key '{key}' not found in info array")
            return v

        def _parse_datetime(key: str) -> Optional[datetime.datetime]:
            v = raw.get(key)
            if v is None:
                return None
            return _parse_zimpol_datetime(v)

        def _parse_float(key: str) -> Optional[float]:
            v = raw.get(key)
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        wavelength = int(_get_required("measurement.wavelength"))
        datetime_start = _parse_zimpol_datetime(_get_required("measurement.datetime"))

        instance = MeasurementMetadata(
            wavelength=wavelength,
            datetime_start=datetime_start,
            datetime_end=_parse_datetime("measurement.datetime.end"),
            telescope_name=_get_required("measurement.telescope name"),
            instrument=_get_required("measurement.instrument"),
            measurement_name=_get_required("measurement.name"),
            measurement_type=_get_required("measurement.type"),
            measurement_id=_get_required("measurement.id"),
            observer=raw.get("measurement.observer", ""),
            project=raw.get("measurement.project", ""),
            camera_identity=raw.get("measurement.camera.identity", ""),
            camera_ccd=raw.get("measurement.camera.CCD", ""),
            camera_temperature=_parse_float("measurement.camera.temperature"),
            integration_time=_parse_float("measurement.integration time"),
            images=raw.get("measurement.images", ""),
            solar_p0=_parse_float("measurement.sun.p0"),
            solar_disc_coordinates=_get("measurement.solar_disc.coordinates"),
            derotator_position_angle=_parse_float(
                "measurement.derotator.position_angle"
            ),
            derotator_offset=_parse_float("measurement.derotator.offset"),
            derotator_coordinate_system=_get("measurement.derotator.coordinate_system"),
            spectrograph_slit=_get("measurement.spectrograph.slit"),
            reduction_outfname=_get("reduction.outfname"),
        )
        instance._raw = raw
        return instance

    def get_raw(self, key: str) -> Optional[str]:
        """Access any raw metadata key that is not explicitly modeled."""
        return self._raw.get(key)


def _decode_info(info: np.ndarray) -> dict[str, str]:
    """Decode an Nx2 byte array into a ``{key: value}`` dict of strings."""
    result: dict[str, str] = {}
    for row in info:
        key = row[0]
        value = row[1]
        k = key.decode("UTF-8") if isinstance(key, bytes) else str(key)
        v = value.decode("UTF-8") if isinstance(value, bytes) else str(value)
        result[k] = v
    return result


def _parse_zimpol_datetime(dt_str: str) -> datetime.datetime:
    """Parse a ZIMPOL datetime string.

    Format is typically ``"2024-07-13T10:22:00+01"`` (with timezone
    offset).
    """
    value = dt_str.strip()
    if not value:
        raise ValueError("Empty datetime string")

    # Accept common ZIMPOL timezone variants: +H, +HH, +HHMM, +HH:MM, and Z.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    m = re.search(r"([+-])(\d{1,4})(:?\d{2})?$", value)
    if m:
        sign, hour_digits, minute_part = m.groups()
        if minute_part is not None and minute_part.startswith(":"):
            minutes = minute_part[1:]
            hours = hour_digits.zfill(2)
        elif minute_part is not None:
            hours = hour_digits.zfill(2)
            minutes = minute_part
        elif len(hour_digits) <= 2:
            hours = hour_digits.zfill(2)
            minutes = "00"
        else:
            hours = hour_digits[:2]
            minutes = hour_digits[2:].ljust(2, "0")[:2]

        value = f"{value[: m.start()]}{sign}{hours}:{minutes}"

    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid ZIMPOL datetime string: {dt_str!r}") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.timezone.utc)

    return parsed.astimezone(datetime.timezone.utc)


class StokesParameters(BaseModel):
    """The four Stokes parameters: I, Q, U, V."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    i: np.ndarray
    q: np.ndarray
    u: np.ndarray
    v: np.ndarray

    def __iter__(self):
        """Allow unpacking: i, q, u, v = stokes."""
        return iter((self.i, self.q, self.u, self.v))


class ObservationDay(BaseModel):
    """Represents a single observation day directory."""

    model_config = ConfigDict(frozen=True)

    path: Path
    raw_dir: Path
    reduced_dir: Path
    processed_dir: Path

    @property
    def name(self) -> str:
        return self.path.name


class MaxDeltaPolicy(BaseModel):
    """Policy for determining the maximum time delta for flat-field matching.

    The default policy applies the same max_delta to all measurements.
    Subclass or replace this to implement per-wavelength or per-
    instrument policies.
    """

    default_max_delta: datetime.timedelta = Field(
        default_factory=lambda: DEFAULT_MAX_DELTA
    )

    def get_max_delta(
        self,
        wavelength: int,
        instrument: str = "",
        telescope: str = "",
    ) -> datetime.timedelta:
        """Return the max time delta for a given measurement context.

        Override this method to implement different thresholds based on
        wavelength, instrument, telescope, etc.

        Args:
            wavelength: Measurement wavelength in Angstrom.
            instrument: Instrument name.
            telescope: Telescope name.

        Returns:
            Maximum allowed timedelta.
        """
        return self.default_max_delta


class DayProcessingResult(BaseModel):
    """Summary of processing a single observation day."""

    day_name: str
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def total_measurements(self) -> int:
        return self.processed + self.skipped + self.failed


class ScanResult(BaseModel):
    """Result of scanning a dataset root."""

    model_config = ConfigDict(frozen=True)

    observation_days: list[ObservationDay]
    pending_measurements: dict[str, list[Path]]  # day_name -> [measurement_paths]
    total_measurements: int
    total_pending: int
