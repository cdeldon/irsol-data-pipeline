"""Tests for filesystem discovery utilities."""

from irsol_data_pipeline.io.filesystem import (
    OBSERVATION_PATTERN,
    FLATFIELD_PATTERN,
    discover_observation_days,
    discover_measurement_files,
    discover_flatfield_files,
    get_processed_stem,
    is_measurement_processed,
)


class TestPatterns:
    def test_observation_pattern_matches(self):
        assert OBSERVATION_PATTERN.match("6302_m1.dat")
        assert OBSERVATION_PATTERN.match("4078_m12.dat")
        assert OBSERVATION_PATTERN.match("5886_m1.dat")

    def test_observation_pattern_rejects(self):
        assert not OBSERVATION_PATTERN.match("ff6302_m1.dat")
        assert not OBSERVATION_PATTERN.match("cal6302_m1.dat")
        assert not OBSERVATION_PATTERN.match("dark6302_m1.dat")
        assert not OBSERVATION_PATTERN.match("6302_m1.sav")

    def test_flatfield_pattern_matches(self):
        assert FLATFIELD_PATTERN.match("ff6302_m1.dat")
        assert FLATFIELD_PATTERN.match("ff4078_m3.dat")

    def test_flatfield_pattern_rejects(self):
        assert not FLATFIELD_PATTERN.match("6302_m1.dat")
        assert not FLATFIELD_PATTERN.match("cal6302_m1.dat")


class TestDiscoverObservationDays:
    def test_discovers_days(self, tmp_path):
        # Create: root/2024/240713/reduced/
        day_dir = tmp_path / "2024" / "240713"
        (day_dir / "reduced").mkdir(parents=True)
        (day_dir / "raw").mkdir(parents=True)

        days = discover_observation_days(tmp_path)
        assert len(days) == 1
        assert days[0].name == "240713"

    def test_skips_dirs_without_reduced(self, tmp_path):
        day_dir = tmp_path / "2024" / "240713"
        day_dir.mkdir(parents=True)

        days = discover_observation_days(tmp_path)
        assert len(days) == 0

    def test_multiple_years(self, tmp_path):
        for year, day in [("2024", "240713"), ("2025", "251111")]:
            d = tmp_path / year / day
            (d / "reduced").mkdir(parents=True)

        days = discover_observation_days(tmp_path)
        assert len(days) == 2

    def test_nonexistent_root(self, tmp_path):
        days = discover_observation_days(tmp_path / "nonexistent")
        assert len(days) == 0


class TestDiscoverMeasurementFiles:
    def test_finds_measurements(self, tmp_path):
        (tmp_path / "6302_m1.dat").touch()
        (tmp_path / "6302_m2.dat").touch()
        (tmp_path / "ff6302_m1.dat").touch()
        (tmp_path / "cal6302_m1.dat").touch()
        (tmp_path / "dark2000_m1.dat").touch()

        files = discover_measurement_files(tmp_path)
        names = [f.name for f in files]
        assert "6302_m1.dat" in names
        assert "6302_m2.dat" in names
        assert "ff6302_m1.dat" not in names
        assert "cal6302_m1.dat" not in names
        assert "dark2000_m1.dat" not in names

    def test_empty_dir(self, tmp_path):
        files = discover_measurement_files(tmp_path)
        assert len(files) == 0

    def test_nonexistent_dir(self, tmp_path):
        files = discover_measurement_files(tmp_path / "nonexistent")
        assert len(files) == 0


class TestDiscoverFlatfieldFiles:
    def test_finds_flatfields(self, tmp_path):
        (tmp_path / "ff6302_m1.dat").touch()
        (tmp_path / "ff4078_m1.dat").touch()
        (tmp_path / "6302_m1.dat").touch()

        files = discover_flatfield_files(tmp_path)
        names = [f.name for f in files]
        assert "ff6302_m1.dat" in names
        assert "ff4078_m1.dat" in names
        assert "6302_m1.dat" not in names


class TestGetProcessedStem:
    def test_basic(self):
        assert get_processed_stem("6302_m1.dat") == "6302_m1"

    def test_with_prefix(self):
        assert get_processed_stem("ff6302_m1.dat") == "ff6302_m1"


class TestIsMeasurementProcessed:
    def test_not_processed(self, tmp_path):
        assert not is_measurement_processed(tmp_path, "6302_m1.dat")

    def test_corrected_exists(self, tmp_path):
        (tmp_path / "6302_m1_corrected.dat.npz").touch()
        assert is_measurement_processed(tmp_path, "6302_m1.dat")

    def test_error_exists(self, tmp_path):
        (tmp_path / "6302_m1_error.json").touch()
        assert is_measurement_processed(tmp_path, "6302_m1.dat")
