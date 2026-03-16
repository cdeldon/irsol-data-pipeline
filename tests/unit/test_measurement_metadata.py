"""Tests for core metadata abstraction."""

import datetime

import numpy as np
import pytest

from irsol_data_pipeline.core.models import (
    MeasurementMetadata,
    _decode_info,
    _parse_zimpol_datetime,
)


def _make_info_array(entries: dict[str, str]) -> np.ndarray:
    """Helper: create a ZIMPOL-style info array from a dict."""
    rows = []
    for k, v in entries.items():
        rows.append([k.encode("UTF-8"), v.encode("UTF-8")])
    return np.array(rows, dtype=object)


class TestDecodeInfo:
    def test_basic_decoding(self):
        info = _make_info_array({"key1": "val1", "key2": "val2"})
        result = _decode_info(info)
        assert result == {"key1": "val1", "key2": "val2"}

    def test_empty_array(self):
        info = np.array([], dtype=object).reshape(0, 2)
        result = _decode_info(info)
        assert result == {}


class TestParseZimpolDatetime:
    def test_with_offset(self):
        dt_result = _parse_zimpol_datetime("2024-07-13T10:22:00+01")
        assert dt_result.year == 2024
        assert dt_result.month == 7
        assert dt_result.hour == 9  # 10 - 1 hour offset
        assert dt_result.tzinfo == datetime.timezone.utc

    def test_without_offset(self):
        dt_result = _parse_zimpol_datetime("2024-07-13T10:22:00")
        assert dt_result.hour == 10
        assert dt_result.tzinfo == datetime.timezone.utc


class TestMeasurementMetadata:
    @pytest.fixture
    def sample_info(self):
        return _make_info_array(
            {
                "measurement.wavelength": "6302",
                "measurement.datetime": "2024-07-13T10:22:00+01",
                "measurement.datetime.end": "2024-07-13T10:25:00+01",
                "measurement.telescope name": "IRSOL",
                "measurement.instrument": "ZIMPOL",
                "measurement.name": "6302_m1",
                "measurement.type": "observation",
                "measurement.id": "1720865520",
                "measurement.observer": "Test Observer",
                "measurement.project": "TestProject",
                "measurement.camera.identity": "CAM1",
                "measurement.camera.CCD": "CCD123",
                "measurement.camera.temperature": "-20.5",
                "measurement.integration time": "0.35",
                "measurement.images": "100 100",
                "measurement.sun.p0": "3.14",
                "measurement.solar_disc.coordinates": "100.0 200.0",
                "measurement.derotator.position_angle": "45.0",
                "measurement.derotator.offset": "0.5",
                "measurement.derotator.coordinate_system": "0",
                "measurement.spectrograph.slit": "0.06",
                "reduction.outfname": "6302_m1.dat",
            }
        )

    def test_from_info_array(self, sample_info):
        meta = MeasurementMetadata.from_info_array(sample_info)
        assert meta.wavelength == 6302
        assert meta.telescope_name == "IRSOL"
        assert meta.instrument == "ZIMPOL"
        assert meta.measurement_name == "6302_m1"
        assert meta.camera_temperature == -20.5
        assert meta.integration_time == 0.35
        assert meta.solar_p0 == 3.14
        assert meta.derotator_position_angle == 45.0

    def test_missing_optional_fields(self):
        info = _make_info_array(
            {
                "measurement.wavelength": "5886",
                "measurement.datetime": "2024-11-11T08:00:00+00",
                "measurement.telescope name": "GREGOR",
                "measurement.instrument": "ZIMPOL",
                "measurement.name": "5886_m1",
                "measurement.type": "observation",
                "measurement.id": "12345",
            }
        )
        meta = MeasurementMetadata.from_info_array(info)
        assert meta.wavelength == 5886
        assert meta.camera_temperature is None
        assert meta.spectrograph_slit is None
        assert meta.derotator_position_angle is None

    def test_missing_required_field_raises(self):
        info = _make_info_array({"measurement.datetime": "2024-01-01T00:00:00+00"})
        with pytest.raises(KeyError, match="measurement.wavelength"):
            MeasurementMetadata.from_info_array(info)

    def test_get_raw(self, sample_info):
        meta = MeasurementMetadata.from_info_array(sample_info)
        assert meta.get_raw("measurement.observer") == "Test Observer"
        assert meta.get_raw("nonexistent.key") is None
