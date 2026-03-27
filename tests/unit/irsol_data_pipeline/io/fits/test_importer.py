from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from irsol_data_pipeline.core.models import (
    CalibrationResult,
    MeasurementMetadata,
    StokesParameters,
)
from irsol_data_pipeline.io import dat as dat_io
from irsol_data_pipeline.io import fits as fits_io
from irsol_data_pipeline.io.fits.exporter import write_stokes_fits


class TestFitsImporter:
    @pytest.fixture(scope="module")
    def fits_path(self, fixture_dir: Path) -> Path:
        return fixture_dir / "5886_m13.fits"

    def test_read_valid_fits(self, fits_path: Path):
        fits_data = fits_io.read(fits_path)

        assert isinstance(fits_data.stokes, StokesParameters)
        assert isinstance(fits_data.calibration, (CalibrationResult, type(None)))


class TestFitsMeasurementMetadataRoundtrip:
    """Tests that MeasurementMetadata survives a .dat → FITS → reload round-
    trip."""

    @pytest.fixture(scope="class")
    def dat_path(self, fixture_dir: Path) -> Path:
        return fixture_dir / "5886_m14.dat"

    @pytest.fixture(scope="class")
    def dat_metadata(self, dat_path: Path) -> MeasurementMetadata:
        """Load MeasurementMetadata from the .dat fixture file."""
        _stokes, info = dat_io.read(dat_path)
        return MeasurementMetadata.from_info_array(info)

    @pytest.fixture(scope="class")
    def dat_stokes(self, dat_path: Path) -> StokesParameters:
        """Load Stokes parameters from the .dat fixture file."""
        stokes, _info = dat_io.read(dat_path)
        return stokes

    @pytest.fixture(scope="class")
    def fits_metadata(
        self,
        tmp_path_factory,
        dat_stokes: StokesParameters,
        dat_metadata: MeasurementMetadata,
    ) -> MeasurementMetadata:
        """Write a FITS file from dat data, reload it, and return the recovered
        metadata."""
        tmp_path = tmp_path_factory.mktemp("fits_roundtrip")
        fits_path = tmp_path / "roundtrip.fits"
        write_stokes_fits(
            output_path=fits_path,
            stokes=dat_stokes,
            info=dat_metadata,
        )
        loaded = fits_io.read(fits_path)
        assert loaded.metadata is not None, (
            "Expected metadata to be extracted from FITS"
        )
        return loaded.metadata

    def test_telescope_name(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.telescope_name == dat_metadata.telescope_name

    def test_instrument(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.instrument == dat_metadata.instrument

    def test_type(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.type == dat_metadata.type

    def test_id(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.id == dat_metadata.id

    def test_name(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.name == dat_metadata.name

    def test_wavelength(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.wavelength == dat_metadata.wavelength

    def test_datetime_start(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        expected = dat_metadata.datetime_start.astimezone(datetime.timezone.utc)
        actual = fits_metadata.datetime_start.astimezone(datetime.timezone.utc)
        assert actual == expected

    def test_datetime_end(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        if dat_metadata.datetime_end is None:
            assert fits_metadata.datetime_end is None
        else:
            expected = dat_metadata.datetime_end.astimezone(datetime.timezone.utc)
            actual = fits_metadata.datetime_end
            assert actual is not None
            assert actual.astimezone(datetime.timezone.utc) == expected

    def test_observer(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.observer == dat_metadata.observer

    def test_project(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.project == dat_metadata.project

    def test_integration_time(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.integration_time == pytest.approx(
            dat_metadata.integration_time
        )

    def test_camera_identity(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.camera.identity == dat_metadata.camera.identity

    def test_camera_ccd(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.camera.ccd == dat_metadata.camera.ccd

    def test_camera_temperature(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        assert fits_metadata.camera.temperature == pytest.approx(
            dat_metadata.camera.temperature
        )

    def test_solar_p0(
        self, dat_metadata: MeasurementMetadata, fits_metadata: MeasurementMetadata
    ):
        if dat_metadata.solar_p0 is not None:
            assert fits_metadata.solar_p0 == pytest.approx(dat_metadata.solar_p0)
