"""Tests for FITS export helpers."""

from __future__ import annotations

from typing import cast

import numpy as np
from astropy.io import fits

from irsol_data_pipeline.core.models import CalibrationResult, StokesParameters
from irsol_data_pipeline.io.fits.exporter import write_stokes_fits


def _make_info_array() -> np.ndarray:
    return np.array(
        [
            ["measurement.wavelength", "6302"],
            ["measurement.datetime", "2024-07-13T10:22:00+01"],
            ["measurement.telescope name", "IRSOL"],
            ["measurement.instrument", "ZIMPOL"],
            ["measurement.name", "map_01"],
            ["measurement.type", "science"],
            ["measurement.id", "m1"],
            ["measurement.observer", "Test Observer"],
            ["measurement.project", "Test Project"],
            ["measurement.camera.identity", "Cam-1"],
            ["measurement.camera.CCD", "CCD-1"],
            ["measurement.integration time", "0.5"],
            ["measurement.images", "1 1"],
        ],
        dtype=object,
    )


def test_write_stokes_fits_writes_processed_measurement(tmp_path):
    output_path = tmp_path / "6302_m1_corrected.fits"
    stokes = StokesParameters(
        i=np.arange(20, dtype=float).reshape(4, 5) + 10.0,
        q=np.full((4, 5), 0.1),
        u=np.full((4, 5), 0.2),
        v=np.full((4, 5), -0.1),
    )
    calibration = CalibrationResult(
        pixel_scale=0.012,
        wavelength_offset=6301.5,
        pixel_scale_error=0.001,
        wavelength_offset_error=0.01,
        reference_file="reference.npy",
    )

    result = write_stokes_fits(
        output_path=output_path,
        stokes=stokes,
        info=_make_info_array(),
        calibration=calibration,
    )

    assert result == output_path
    assert output_path.exists()

    with fits.open(output_path) as hdul:
        stokes_i_hdu = cast(fits.ImageHDU, hdul[1])
        assert len(hdul) == 5
        assert stokes_i_hdu.header["EXTNAME"] == "Stokes I"
        assert stokes_i_hdu.header["WAVECAL"] == 1
        assert stokes_i_hdu.header["WAVELNTH"] == 6302
        assert stokes_i_hdu.data.shape == (5, 4, 1)


def test_write_stokes_fits_omits_calibration_metadata_when_not_provided(tmp_path):
    output_path = tmp_path / "6302_m2_corrected.fits"
    stokes = StokesParameters(
        i=np.arange(20, dtype=float).reshape(4, 5) + 10.0,
        q=np.full((4, 5), 0.1),
        u=np.full((4, 5), 0.2),
        v=np.full((4, 5), -0.1),
    )

    write_stokes_fits(
        output_path=output_path,
        stokes=stokes,
        info=_make_info_array(),
    )

    with fits.open(output_path) as hdul:
        stokes_i_hdu = cast(fits.ImageHDU, hdul[1])
        assert "WAVECAL" not in stokes_i_hdu.header
