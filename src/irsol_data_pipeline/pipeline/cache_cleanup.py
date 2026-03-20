"""Cache-file cleanup logic for observation day directories.

Contains the pure filesystem operations for discovering and removing stale
``.pkl`` files from the per-day cache directories (``processed/_cache`` and
``processed/_sdo_cache``).  All orchestration concerns live in the
``orchestration/flows/maintenance`` layer.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from loguru import logger

from irsol_data_pipeline.core.models import CacheCleanupDayResult, ObservationDay
from irsol_data_pipeline.pipeline.filesystem import (
    processed_cache_dir_for_day,
    sdo_cache_dir_for_day,
)

_UNITS = [("TB", 1 << 40), ("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)]


def _format_bytes(n: int) -> str:
    """Return a human-readable byte size string.

    Args:
        n: Size in bytes.

    Returns:
        Human-readable string such as ``"1.23 MB"`` or ``"512 B"``.
    """
    for suffix, threshold in _UNITS:
        if n >= threshold:
            return f"{n / threshold:.2f} {suffix}"
    return f"{n} B"


def _cache_directories_for_day(day_path: Path) -> list[Path]:
    """Return existing cache directories for an observation day.

    Args:
        day_path: Observation day path.

    Returns:
        Subset of ``[processed/_cache, processed/_sdo_cache]`` that exist on
        disk.
    """
    candidates = [
        processed_cache_dir_for_day(day_path),
        sdo_cache_dir_for_day(day_path),
    ]
    return [d for d in candidates if d.is_dir()]


def cleanup_day_cache_files(
    day: ObservationDay,
    hours: float,
) -> CacheCleanupDayResult:
    """Delete stale ``.pkl`` cache files for a single observation day.

    Files in ``processed/_cache`` and ``processed/_sdo_cache`` whose
    last-modified time is older than *hours* are removed.  Non-``.pkl``
    files are always left untouched.

    Args:
        day: Observation day to clean up.
        hours: Retention window in hours.  Files older than
            ``now - hours`` are deleted.

    Returns:
        Cleanup summary for the day.
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        hours=hours
    )

    with logger.contextualize(day=day.name, hours=hours, cutoff=cutoff.isoformat()):
        checked = 0
        deleted = 0
        deleted_bytes = 0
        skipped_recent = 0
        skipped_bytes = 0
        failed = 0

        cache_dirs = _cache_directories_for_day(day.path)
        logger.info(
            "Starting day cache cleanup",
            cache_directories=[str(d) for d in cache_dirs],
        )

        for cache_dir in cache_dirs:
            logger.debug("Scanning cache directory", cache_dir=cache_dir)
            pkl_files = sorted(cache_dir.glob("*.pkl"))
            logger.debug(
                "Found .pkl files in cache directory",
                cache_dir=cache_dir,
                count=len(pkl_files),
            )
            for cache_file in pkl_files:
                checked += 1
                stat = cache_file.stat()
                file_size = stat.st_size
                modified_at = datetime.datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=datetime.timezone.utc,
                )
                logger.trace(
                    "Checking cache file age",
                    file=cache_file.name,
                    modified_at=modified_at.isoformat(),
                    is_stale=modified_at < cutoff,
                )
                if modified_at >= cutoff:
                    skipped_recent += 1
                    skipped_bytes += file_size
                    logger.debug(
                        "Keeping recent cache file",
                        file=cache_file.name,
                        modified_at=modified_at.isoformat(),
                    )
                    continue
                try:
                    cache_file.unlink()
                    deleted += 1
                    deleted_bytes += file_size
                    logger.info(
                        "Deleted old cache file",
                        file=cache_file.name,
                        modified_at=modified_at.isoformat(),
                        size_bytes=file_size,
                    )
                except OSError:
                    failed += 1
                    logger.exception(
                        "Failed deleting cache file",
                        file=str(cache_file),
                    )

        result = CacheCleanupDayResult(
            day_name=day.name,
            checked_files=checked,
            deleted_files=deleted,
            deleted_bytes=deleted_bytes,
            skipped_recent_files=skipped_recent,
            skipped_bytes=skipped_bytes,
            failed_files=failed,
        )
        logger.info(
            "Completed day cache cleanup",
            checked_files=result.checked_files,
            deleted_files=result.deleted_files,
            deleted_bytes=result.deleted_bytes,
            skipped_recent_files=result.skipped_recent_files,
            skipped_bytes=result.skipped_bytes,
            failed_files=result.failed_files,
        )
        return result


def build_cache_cleanup_report(
    root: Path,
    results: list[CacheCleanupDayResult],
    hours: float,
) -> str:
    """Build a markdown summary of a cache-cleanup run.

    Generates a human-readable report suitable for use as a Prefect artifact
    or for writing to disk, summarising what was deleted, skipped, and failed
    across all observation days.

    Args:
        root: Dataset root path used as context in the report header.
        results: Per-day cleanup results produced by the orchestration flow.
        hours: Retention window (hours) that was applied during cleanup.

    Returns:
        Multi-line markdown string.
    """
    total_checked = sum(r.checked_files for r in results)
    total_deleted = sum(r.deleted_files for r in results)
    total_deleted_bytes = sum(r.deleted_bytes for r in results)
    total_skipped = sum(r.skipped_recent_files for r in results)
    total_skipped_bytes = sum(r.skipped_bytes for r in results)
    total_failed = sum(r.failed_files for r in results)

    lines = [
        "# Cache Cleanup Report",
        "",
        f"- Root: `{root}`",
        f"- Retention window: `{hours:.1f}` hours",
        f"- Observation days processed: `{len(results)}`",
        "",
        "## Totals",
        "",
        "| Metric | Count | Size |",
        "|---|---:|---:|",
        f"| Checked | `{total_checked}` | — |",
        f"| Deleted | `{total_deleted}` | `{_format_bytes(total_deleted_bytes)}` |",
        f"| Kept (recent) | `{total_skipped}` | `{_format_bytes(total_skipped_bytes)}` |",
        f"| Failed | `{total_failed}` | — |",
        "",
    ]

    if not results:
        lines.append("No observation days were found.")
        return "\n".join(lines)

    lines.extend(
        [
            "## Per-Day Breakdown",
            "",
            "| Day | Checked | Deleted | Deleted Size | Kept | Kept Size | Failed |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in sorted(results, key=lambda x: x.day_name):
        lines.append(
            f"| `{r.day_name}` "
            f"| {r.checked_files} "
            f"| {r.deleted_files} "
            f"| `{_format_bytes(r.deleted_bytes)}` "
            f"| {r.skipped_recent_files} "
            f"| `{_format_bytes(r.skipped_bytes)}` "
            f"| {r.failed_files} |"
        )

    return "\n".join(lines)
