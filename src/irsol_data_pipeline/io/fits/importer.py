"""Import FITS measurement content into typed pipeline structures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from astropy.io import fits
from loguru import logger

from irsol_data_pipeline.core.models import (
    CalibrationResult,
    CameraInfo,
    MeasurementMetadata,
    StokesParameters,
)
from irsol_data_pipeline.exceptions import FitsImportError


@dataclass(frozen=True)
class ImportedFitsMeasurement:
    """Typed representation of a measurement loaded from FITS."""

    stokes: StokesParameters
    calibration: Optional[CalibrationResult]
    header: fits.Header
    metadata: Optional[MeasurementMetadata]


def load_fits_measurement(fits_path: Path) -> ImportedFitsMeasurement:
    """Load Stokes profiles, optional wavelength calibration, and measurement
    metadata from FITS."""
    with logger.contextualize(path=fits_path):
        logger.debug("Loading FITS measurement")
        with fits.open(fits_path) as hdul:
            si_hdu = _get_hdu(hdul, "Stokes I", 1)
            sq_hdu = _get_hdu(hdul, "Stokes Q/I", 2)
            su_hdu = _get_hdu(hdul, "Stokes U/I", 3)
            sv_hdu = _get_hdu(hdul, "Stokes V/I", 4)

            header = si_hdu.header.copy()
            primary_header = hdul[0].header.copy()
            stokes = StokesParameters(
                i=_to_spatial_spectral(si_hdu.data),
                q=_to_spatial_spectral(sq_hdu.data),
                u=_to_spatial_spectral(su_hdu.data),
                v=_to_spatial_spectral(sv_hdu.data),
            )
            calibration = _extract_calibration(header)
            metadata = _extract_metadata(header, primary_header)

        logger.debug(
            "Loaded FITS measurement",
            has_calibration=calibration is not None,
            has_metadata=metadata is not None,
            shape_i=stokes.i.shape,
            shape_q=stokes.q.shape,
            shape_u=stokes.u.shape,
            shape_v=stokes.v.shape,
        )

    return ImportedFitsMeasurement(
        stokes=stokes,
        calibration=calibration,
        header=header,
        metadata=metadata,
    )


def _extract_metadata(
    header: fits.Header,
    primary_header: Optional[fits.Header] = None,
) -> Optional[MeasurementMetadata]:
    """Build a MeasurementMetadata from FITS header fields written by
    write_stokes_fits.

    ``header`` is the Stokes I data extension header, which contains most
    observation fields.  ``primary_header`` is the primary HDU header, which
    holds ``CAMTEMP`` and ``SOLAR_P0``; when provided those values are
    preferred over any copies in ``header``.

    Only the subset of fields that are stored in the FITS header is populated.
    Returns ``None`` when any required field is absent.
    """
    telescope_name = header.get("TELESCOP")
    instrument = header.get("INSTRUME")
    measurement_type = header.get("DATATYPE")
    measurement_id = header.get("POINT_ID")
    wavelength = header.get("WAVELNTH")
    name = header.get("MEASNAME")
    date_beg = header.get("DATE-BEG")

    required = {
        "TELESCOP": telescope_name,
        "INSTRUME": instrument,
        "DATATYPE": measurement_type,
        "POINT_ID": measurement_id,
        "WAVELNTH": wavelength,
        "MEASNAME": name,
        "DATE-BEG": date_beg,
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        logger.debug(
            "FITS header missing required fields for MeasurementMetadata",
            missing_fields=missing,
        )
        return None

    date_end_raw = header.get("DATE-END")
    date_end = _as_str(date_end_raw)

    # CAMTEMP and SOLAR_P0 are written to the primary HDU header; fall back to
    # the data header for files that may have copied them there.
    camera_temp = _as_float(_from_primary_or_data(primary_header, header, "CAMTEMP"))
    solar_p0_val = _as_float(_from_primary_or_data(primary_header, header, "SOLAR_P0"))

    data: dict[str, object] = {
        "telescope_name": str(telescope_name),
        "instrument": str(instrument),
        "type": str(measurement_type),
        "id": int(measurement_id),
        "wavelength": int(wavelength),
        "name": str(name),
        "datetime_start": str(date_beg),
        "datetime_end": date_end,
        "observer": _as_str(header.get("OBSERVER")) or "",
        "project": _as_str(header.get("PROJECT")) or "",
        "integration_time": _as_float(header.get("TEXPOSUR")),
        "solar_p0": solar_p0_val,
        "camera": CameraInfo(
            identity=_as_str(header.get("CAMERA")),
            ccd=_as_str(header.get("CCD")),
            temperature=camera_temp,
        ),
    }

    try:
        return MeasurementMetadata.model_validate(data)
    except Exception:
        logger.exception("Failed to build MeasurementMetadata from FITS header")
        return None


def _extract_calibration(header: fits.Header) -> Optional[CalibrationResult]:
    """Read calibration values from FITS headers when available."""
    wavecal_value = header.get("WAVECAL", 0)
    has_calibration = False

    if isinstance(wavecal_value, (int, float)):
        has_calibration = int(wavecal_value) == 1
    elif isinstance(wavecal_value, str):
        has_calibration = wavecal_value.strip() == "1"

    if not has_calibration:
        logger.debug("No FITS calibration metadata present (WAVECAL != 1)")
        return None

    a0 = _as_float(header.get("CRVAL3"))
    a1 = _as_float(header.get("CDELT3"))
    if a0 is None or a1 is None:
        logger.debug("Incomplete FITS calibration metadata", crval3=a0, cdelt3=a1)
        return None

    a1_err = _as_float(header.get("CRDER3"))
    a0_err = _as_float(header.get("CSYER3"))

    return CalibrationResult(
        pixel_scale=a1,
        wavelength_offset=a0,
        pixel_scale_error=a1_err if a1_err is not None else 0.0,
        wavelength_offset_error=a0_err if a0_err is not None else 0.0,
        reference_file="fits-header",
    )


def _get_hdu(hdul: fits.HDUList, extname: str, fallback_index: int) -> fits.ImageHDU:
    """Get a Stokes image extension by name, falling back to index."""
    for hdu in hdul:
        if isinstance(hdu, fits.ImageHDU) and hdu.header.get("EXTNAME") == extname:
            return hdu

    hdu = hdul[fallback_index]
    if not isinstance(hdu, fits.ImageHDU):
        raise FitsImportError(
            f"Expected ImageHDU at index {fallback_index} for {extname}"
        )
    return hdu


def _to_spatial_spectral(data: np.ndarray) -> np.ndarray:
    """Convert FITS image data to (spatial, spectral) arrays for plotting."""
    arr = np.asarray(data)
    arr = np.squeeze(arr)
    if arr.ndim != 2:
        raise FitsImportError(
            f"Expected 2D Stokes image after squeeze, got shape {arr.shape}"
        )
    return arr.T


def _as_float(value: object) -> Optional[float]:
    """Convert header value to float when possible."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_str(value: object) -> Optional[str]:
    """Convert a FITS header value to a non-empty stripped string, or None.

    Returns ``None`` when ``value`` is ``None`` or reduces to an empty string
    after stripping whitespace.  Accepts any FITS header value type (str,
    int, float, or None).
    """
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _from_primary_or_data(
    primary: Optional[fits.Header],
    data: fits.Header,
    key: str,
) -> object:
    """Look up a header key preferring the primary HDU, falling back to a data
    HDU.

    Some fields (e.g. ``CAMTEMP``, ``SOLAR_P0``) are written exclusively to
    the primary HDU by :func:`write_stokes_fits`.  This helper transparently
    falls back to the data extension header so that callers need not repeat
    the fallback logic for every such field.
    """
    if primary is not None:
        value = primary.get(key)
        if value is not None:
            return value
    return data.get(key)
