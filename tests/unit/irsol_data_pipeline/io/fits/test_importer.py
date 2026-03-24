from pathlib import Path

import pytest

from irsol_data_pipeline.core.models import CalibrationResult, StokesParameters
from irsol_data_pipeline.io import fits as fits_io


class TestFitsImporter:
    @pytest.fixture(scope="module")
    def fits_path(self, fixture_dir: Path) -> Path:
        return fixture_dir / "5886_m13.fits"

    def test_read_valid_fits(self, fits_path: Path):
        fits_data = fits_io.read(fits_path)

        assert isinstance(fits_data.stokes, StokesParameters)
        assert isinstance(fits_data.calibration, (CalibrationResult, type(None)))
