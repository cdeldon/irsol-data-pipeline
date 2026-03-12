from prefect.logging import get_run_logger
from irsol_data_pipeline.logging_config import (
    LOG_LEVEL,
    setup_logging as _setup_base_logging,
)

import logging as stdlib_logging
from loguru import logger


_prefect_sink_added = False


def setup_logging(level: LOG_LEVEL = "DEBUG"):
    """Configure loguru logging with a Prefect sink that forwards logs to the run logger."""
    global _prefect_sink_added
    _setup_base_logging(level=level)

    if _prefect_sink_added:
        return

    def _prefect_sink(message):
        record = message.record
        try:
            run_logger = get_run_logger()
        except Exception:
            return  # Not inside a flow/task run context

        # loguru and stdlib share numeric levels (DEBUG=10, INFO=20, etc.)
        # Map loguru-only levels: TRACE(5)->DEBUG(10), SUCCESS(25)->INFO(20)
        level_no = record["level"].no
        if level_no < stdlib_logging.DEBUG:
            level_no = stdlib_logging.DEBUG
        elif level_no == 25:  # SUCCESS
            level_no = stdlib_logging.INFO

        run_logger.log(level_no, str(message).rstrip())

    logger.add(_prefect_sink, format="{message}", level=level)
    _prefect_sink_added = True
