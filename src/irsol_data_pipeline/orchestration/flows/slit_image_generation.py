"""Prefect 3.x orchestration flows for slit image generation.

Two flows:
1. generate_slit_images — Scans dataset root and generates slit previews for all days
2. generate_daily_slit_images — Generates slit previews for a single observation day
"""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger
from prefect import flow, task
from prefect.futures import as_completed
from prefect.task_runners import ThreadPoolTaskRunner

from irsol_data_pipeline.core.config import JSOC_EMAIL
from irsol_data_pipeline.core.models import (
    DayProcessingResult,
    ObservationDay,
)
from irsol_data_pipeline.orchestration.patch_logging import setup_logging
from irsol_data_pipeline.orchestration.utils import create_prefect_markdown_report
from irsol_data_pipeline.pipeline.filesystem import (
    discover_observation_days,
    processed_dir_for_day,
    raw_dir_for_day,
    reduced_dir_for_day,
)
from irsol_data_pipeline.slit_images.processor import generate_slit_images_for_day


@task(task_run_name="generate-slit-images-for-day/{day_path.name}")
def run_day_slit_generation_task(
    day_path: Path,
    jsoc_email: str,
    use_limbguider: bool = False,
) -> DayProcessingResult:
    """Prefect task: generate slit images for a single day."""
    return generate_daily_slit_images(
        day_path=day_path,
        jsoc_email=jsoc_email,
        use_limbguider=use_limbguider,
    )


@flow(
    flow_run_name="generate-slit-images/{root}",
    description="Scans the dataset and generates slit preview images for all observation days",
)
def generate_slit_images(
    root: str,
    jsoc_email: str = "",
    use_limbguider: bool = False,
    max_concurrent_days: int = max(1, min(4, (os.cpu_count() or 1) - 1)),
) -> list[DayProcessingResult]:
    """Scan the dataset and generate slit preview images for all days.

    Args:
        root: Dataset root path.
        jsoc_email: JSOC email for DRMS queries. Falls back to
            ``JSOC_EMAIL`` from ``core.config``.
        use_limbguider: Whether to try using limbguider coordinates.
        max_concurrent_days: Maximum number of concurrent day processing
            tasks. Defaults to CPU count - 1, capped at 4
            (lower than flat-field correction due to network I/O).

    Returns:
        List of DayProcessingResult for each processed day.
    """
    setup_logging()

    email = jsoc_email or JSOC_EMAIL
    if not email:
        logger.error("No JSOC email provided. Set JSOC_EMAIL environment variable.")
        return []

    dataset_root = Path(root)
    logger.info("Starting slit image generation", root=root)

    observation_days = discover_observation_days(dataset_root)
    if not observation_days:
        logger.info("No observation days found")
        return []

    logger.info(
        "Found {} observation days, generating slit previews",
        len(observation_days),
    )

    # Build summary report
    summary_lines = [
        "# Slit Image Generation Scan",
        "",
        f"**Root**: `{root}`",
        f"**Observation days**: {len(observation_days)}",
    ]
    create_prefect_markdown_report(
        content="\n".join(summary_lines),
        description="Slit image generation scan summary",
    )

    day_paths = [day.path for day in observation_days]

    with ThreadPoolTaskRunner(max_workers=max_concurrent_days) as runner:
        result_futures = []
        for day_path in day_paths:
            future = runner.submit(
                run_day_slit_generation_task,
                {
                    "day_path": day_path,
                    "jsoc_email": email,
                    "use_limbguider": use_limbguider,
                },
            )
            result_futures.append(future)

        results = []
        for result_future in as_completed(result_futures):
            result = result_future.result()
            results.append(result)

    total_processed = sum(r.processed for r in results)
    total_failed = sum(r.failed for r in results)
    logger.success(
        "Slit image generation complete",
        processed=total_processed,
        failed=total_failed,
        days=len(results),
    )

    return results


@flow(
    flow_run_name="generate-daily-slit-images/{day_path.name}",
    description="Generates slit preview images for a single observation day",
)
def generate_daily_slit_images(
    day_path: Path,
    jsoc_email: str = "",
    use_limbguider: bool = False,
) -> DayProcessingResult:
    """Generate slit preview images for a single observation day.

    Args:
        day_path: Path to the observation day directory.
        jsoc_email: JSOC email for DRMS queries. Falls back to
            ``JSOC_EMAIL`` from ``core.config``.
        use_limbguider: Whether to try using limbguider coordinates.

    Returns:
        DayProcessingResult summary.
    """
    setup_logging()

    email = jsoc_email or JSOC_EMAIL
    if not email:
        logger.error("No JSOC email provided. Set JSOC_EMAIL environment variable.")
        return DayProcessingResult(
            day_name=Path(day_path).name, errors=["No JSOC email"]
        )

    path = Path(day_path)
    day = ObservationDay(
        path=path,
        raw_dir=raw_dir_for_day(path),
        reduced_dir=reduced_dir_for_day(path),
        processed_dir=processed_dir_for_day(path),
    )

    result = generate_slit_images_for_day(
        day=day,
        jsoc_email=email,
        use_limbguider=use_limbguider,
    )

    logger.success(
        "Day slit generation complete",
        day=result.day_name,
        processed=result.processed,
        skipped=result.skipped,
        failed=result.failed,
    )

    return result
