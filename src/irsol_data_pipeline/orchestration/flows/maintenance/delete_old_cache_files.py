"""Maintenance flow for deleting old cache files.

This module defines a top-level flow that dispatches per-day subflows to
remove stale ``.pkl`` files from:

- ``processed/_cache``
- ``processed/_sdo_cache``

Only files older than the configured retention window are deleted.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from irsol_data_pipeline.orchestration.decorators import flow, task
from irsol_data_pipeline.orchestration.patch_logging import setup_logging
from irsol_data_pipeline.pipeline.filesystem import (
    processed_cache_dir_for_day,
    sdo_cache_dir_for_day,
)

DEFAULT_CACHE_RETENTION_HOURS = 24 * 7 * 4


@dataclass(frozen=True)
class CacheCleanupDayResult:
    """Summary of cache-cleanup work performed for one observation day.

    Attributes:
        day_name: Observation day folder name.
        checked_files: Number of ``.pkl`` files found in cache directories.
        deleted_files: Number of stale files successfully deleted.
        skipped_recent_files: Number of recent files kept.
        failed_files: Number of files that could not be deleted.
    """

    day_name: str
    checked_files: int = 0
    deleted_files: int = 0
    skipped_recent_files: int = 0
    failed_files: int = 0


def _discover_observation_day_paths(root: Path) -> list[Path]:
    """Discover ``<root>/<year>/<day>`` folders to process.

    Args:
        root: Dataset root.

    Returns:
        Sorted list of observation-day paths.
    """
    if not root.is_dir():
        return []

    day_paths: list[Path] = []
    for year_path in sorted(root.iterdir()):
        if not year_path.is_dir():
            continue
        for day_path in sorted(year_path.iterdir()):
            if day_path.is_dir():
                day_paths.append(day_path)
    return day_paths


@task(task_run_name="maintenance-cache/discover-days/{root.name}")
def discover_observation_day_paths(root: Path) -> list[Path]:
    """Task wrapper that discovers all observation-day paths.

    Args:
        root: Dataset root.

    Returns:
        Sorted list of observation-day paths.
    """
    day_paths = _discover_observation_day_paths(root)
    logger.info("Discovered observation days", root=root, count=len(day_paths))
    return day_paths


def _cache_directories_for_day(day_path: Path) -> list[Path]:
    """Return the cache directories to inspect for a day.

    Args:
        day_path: Observation day path.

    Returns:
        Existing day cache directories.
    """
    candidate_dirs = [
        processed_cache_dir_for_day(day_path),
        sdo_cache_dir_for_day(day_path),
    ]
    return [cache_dir for cache_dir in candidate_dirs if cache_dir.is_dir()]


@flow(
    name="maintenance-cache-cleanup-daily",
    flow_run_name="maintenance/cache-cleanup/daily/{day_path.name}",
    description="Delete old .pkl cache files for one observation day",
)
def delete_old_day_cache_files(
    day_path: Path,
    hours: float = DEFAULT_CACHE_RETENTION_HOURS,
) -> CacheCleanupDayResult:
    """Delete stale cache files for a single observation day.

    Args:
        day_path: Observation day path.
        hours: Cache retention window in hours.

    Returns:
        Cleanup summary for the day.
    """
    setup_logging()

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        hours=hours
    )
    checked_files = 0
    deleted_files = 0
    skipped_recent_files = 0
    failed_files = 0

    day_path = Path(day_path)
    cache_dirs = _cache_directories_for_day(day_path)
    logger.info(
        "Starting day cache cleanup",
        day=day_path.name,
        hours=hours,
        cache_directories=[str(cache_dir) for cache_dir in cache_dirs],
    )

    for cache_dir in cache_dirs:
        for cache_file in sorted(cache_dir.glob("*.pkl")):
            checked_files += 1

            modified_at = datetime.datetime.fromtimestamp(
                cache_file.stat().st_mtime,
                tz=datetime.timezone.utc,
            )
            if modified_at >= cutoff:
                skipped_recent_files += 1
                continue

            try:
                cache_file.unlink()
                deleted_files += 1
                logger.info(
                    "Deleted old cache file",
                    day=day_path.name,
                    file=cache_file.name,
                    modified_at=modified_at.isoformat(),
                )
            except OSError:
                failed_files += 1
                logger.exception(
                    "Failed deleting cache file",
                    day=day_path.name,
                    file=str(cache_file),
                )

    result = CacheCleanupDayResult(
        day_name=day_path.name,
        checked_files=checked_files,
        deleted_files=deleted_files,
        skipped_recent_files=skipped_recent_files,
        failed_files=failed_files,
    )

    logger.info(
        "Completed day cache cleanup",
        day=result.day_name,
        checked_files=result.checked_files,
        deleted_files=result.deleted_files,
        skipped_recent_files=result.skipped_recent_files,
        failed_files=result.failed_files,
    )
    return result


@flow(
    name="maintenance-cache-cleanup",
    flow_run_name="maintenance/cache-cleanup/{hours}h",
    description=(
        "Delete old .pkl cache files from processed/_cache and processed/_sdo_cache"
    ),
)
def delete_old_cache_files(
    root: str,
    hours: float = DEFAULT_CACHE_RETENTION_HOURS,
) -> list[CacheCleanupDayResult]:
    """Delete stale cache files across all observation days.

    Args:
        root: Dataset root path.
        hours: Cache retention window in hours.

    Returns:
        Per-day cleanup summaries.
    """
    setup_logging()

    root_path = Path(root)
    logger.info("Starting cache cleanup", root=root_path, hours=hours)

    day_paths = discover_observation_day_paths(root_path)
    if not day_paths:
        logger.info("No observation days found for cache cleanup", root=root_path)
        return []

    results = [
        delete_old_day_cache_files(day_path=day_path, hours=hours)
        for day_path in day_paths
    ]

    logger.success(
        "Cache cleanup completed",
        day_count=len(results),
        checked_files=sum(result.checked_files for result in results),
        deleted_files=sum(result.deleted_files for result in results),
        skipped_recent_files=sum(result.skipped_recent_files for result in results),
        failed_files=sum(result.failed_files for result in results),
    )
    return results
