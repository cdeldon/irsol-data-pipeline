"""Tests for core domain models."""

import datetime
from pathlib import Path

import numpy as np
import pytest

from irsol_data_pipeline.core.calibration import CalibrationResult
from irsol_data_pipeline.core.flatfield import FlatField
from irsol_data_pipeline.core.measurement import Measurement
from irsol_data_pipeline.core.metadata import MeasurementMetadata
from irsol_data_pipeline.core.types import StokesParameters


def _make_info_array(entries: dict[str, str]) -> np.ndarray:
    rows = []
    for k, v in entries.items():
        rows.append([k.encode("UTF-8"), v.encode("UTF-8")])
    return np.array(rows, dtype=object)


@pytest.fixture
def sample_metadata():
    info = _make_info_array(
        {
            "measurement.wavelength": "6302",
            "measurement.datetime": "2024-07-13T10:22:00+01",
            "measurement.telescope name": "IRSOL",
            "measurement.instrument": "ZIMPOL",
            "measurement.name": "6302_m1",
            "measurement.type": "observation",
            "measurement.id": "123",
        }
    )
    return MeasurementMetadata.from_info_array(info)


@pytest.fixture
def sample_stokes():
    return StokesParameters(
        i=np.ones((50, 200)),
        q=np.zeros((50, 200)),
        u=np.zeros((50, 200)),
        v=np.zeros((50, 200)),
    )


class TestStokesParameters:
    def test_creation(self, sample_stokes):
        assert sample_stokes.i.shape == (50, 200)
        assert sample_stokes.q.shape == (50, 200)

    def test_unpacking(self, sample_stokes):
        i, q, u, v = sample_stokes
        assert i.shape == (50, 200)


class TestMeasurement:
    def test_properties(self, sample_metadata, sample_stokes):
        m = Measurement(
            source_path=Path("/data/6302_m1.dat"),
            metadata=sample_metadata,
            stokes=sample_stokes,
        )
        assert m.wavelength == 6302
        assert m.name == "6302_m1"
        assert isinstance(m.timestamp, datetime.datetime)


class TestFlatField:
    def test_properties(self, sample_metadata, sample_stokes):
        ff = FlatField(
            source_path=Path("/data/ff6302_m1.dat"),
            metadata=sample_metadata,
            stokes=sample_stokes,
        )
        assert ff.wavelength == 6302
        assert isinstance(ff.timestamp, datetime.datetime)


class TestCalibrationResult:
    def test_pixel_to_wavelength(self):
        cal = CalibrationResult(
            pixel_scale=0.01,
            wavelength_offset=6300.0,
            pixel_scale_error=0.001,
            wavelength_offset_error=0.1,
            reference_file="ref.npy",
        )
        assert cal.pixel_to_wavelength(100) == pytest.approx(6301.0)

    def test_wavelength_to_pixel(self):
        cal = CalibrationResult(
            pixel_scale=0.01,
            wavelength_offset=6300.0,
            pixel_scale_error=0.001,
            wavelength_offset_error=0.1,
            reference_file="ref.npy",
        )
        assert cal.wavelength_to_pixel(6301.0) == pytest.approx(100.0)
