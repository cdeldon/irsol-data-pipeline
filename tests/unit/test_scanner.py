"""Tests for the scanner module."""

from irsol_data_pipeline.pipeline.scanner import scan_dataset


class TestScanDataset:
    def test_empty_root(self, tmp_path):
        result = scan_dataset(tmp_path)
        assert result.total_measurements == 0
        assert result.total_pending == 0
        assert len(result.observation_days) == 0

    def test_discovers_pending(self, tmp_path):
        # Create: root/2024/240713/reduced/6302_m1.dat
        day = tmp_path / "2024" / "240713"
        reduced = day / "reduced"
        reduced.mkdir(parents=True)
        (reduced / "6302_m1.dat").touch()
        (reduced / "6302_m2.dat").touch()
        (reduced / "ff6302_m1.dat").touch()

        result = scan_dataset(tmp_path)
        assert result.total_measurements == 2
        assert result.total_pending == 2
        assert "240713" in result.pending_measurements

    def test_skips_processed(self, tmp_path):
        day = tmp_path / "2024" / "240713"
        reduced = day / "reduced"
        processed = day / "processed"
        reduced.mkdir(parents=True)
        processed.mkdir(parents=True)
        (reduced / "6302_m1.dat").touch()
        (reduced / "6302_m2.dat").touch()
        # Mark m1 as processed
        (processed / "6302_m1_corrected.fits").touch()

        result = scan_dataset(tmp_path)
        assert result.total_measurements == 2
        assert result.total_pending == 1

    def test_skips_errored(self, tmp_path):
        day = tmp_path / "2024" / "240713"
        reduced = day / "reduced"
        processed = day / "processed"
        reduced.mkdir(parents=True)
        processed.mkdir(parents=True)
        (reduced / "6302_m1.dat").touch()
        (processed / "6302_m1_error.json").touch()

        result = scan_dataset(tmp_path)
        assert result.total_pending == 0
