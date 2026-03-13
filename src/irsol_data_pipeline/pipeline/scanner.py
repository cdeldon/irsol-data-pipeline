"""Dataset scanner.

Scans the dataset root to discover observation days that need processing.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from irsol_data_pipeline.core.models import ScanResult
from irsol_data_pipeline.io.filesystem import (
    discover_measurement_files,
    discover_observation_days,
    is_measurement_processed,
)


def scan_dataset(root: Path) -> ScanResult:
    """Scan the dataset root and find measurements that need processing.

    For each observation day, checks the ``reduced/`` folder for
    measurement files and the ``processed/`` folder for existing outputs.
    Only measurements without processed outputs are reported.

    Args:
        root: The dataset root directory.

    Returns:
        ScanResult with discovered days and pending measurements.
    """
    days = discover_observation_days(root)
    pending: dict[str, list[Path]] = {}
    total = 0
    total_pending = 0

    for day in days:
        measurements = discover_measurement_files(day.reduced_dir)
        total += len(measurements)

        unprocessed = [
            m
            for m in measurements
            if not is_measurement_processed(day.processed_dir, m.name)
        ]

        if unprocessed:
            pending[day.name] = unprocessed
            total_pending += len(unprocessed)

        logger.info(
            "Scanned observation day",
            day=day.name,
            measurements=len(measurements),
            pending=len(unprocessed),
        )

    return ScanResult(
        observation_days=days,
        pending_measurements=pending,
        total_measurements=total,
        total_pending=total_pending,
    )
