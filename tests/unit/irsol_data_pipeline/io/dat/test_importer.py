from pathlib import Path

import numpy as np
import pytest

from irsol_data_pipeline.core.models import StokesParameters
from irsol_data_pipeline.exceptions import DatImportError
from irsol_data_pipeline.io import dat as dat_io


class TestImporter:
    @pytest.fixture(scope="module")
    def dat_path(self, fixture_dir: Path) -> Path:
        return fixture_dir / "5886_m14.dat"

    @pytest.fixture(scope="module")
    def invalid_path_extension(self, fixture_dir: Path) -> Path:
        return fixture_dir / "5886_m14.txt"

    @pytest.fixture(scope="module")
    def expected_stokes_shape(self) -> tuple[int, ...]:
        return (140, 1240)

    @pytest.fixture(scope="module")
    def expected_info_shape(self) -> tuple[int, ...]:
        return (65, 2)

    def test_read_valid_dat(
        self,
        dat_path: Path,
        expected_stokes_shape: tuple[int, ...],
        expected_info_shape: tuple[int, ...],
    ):
        stokes, info = dat_io.read(dat_path)
        assert isinstance(stokes, StokesParameters)
        assert isinstance(info, np.ndarray)

        assert stokes.i.shape == expected_stokes_shape
        assert stokes.q.shape == expected_stokes_shape
        assert stokes.u.shape == expected_stokes_shape
        assert stokes.v.shape == expected_stokes_shape
        assert info.shape == expected_info_shape

    def test_read_invalid_dat(self, invalid_path_extension: Path):
        with pytest.raises(DatImportError):
            dat_io.read(invalid_path_extension)
