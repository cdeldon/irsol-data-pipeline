import enum
import logging as stdlib_logging
import traceback

from loguru import logger
from prefect.logging import get_run_logger

from irsol_data_pipeline.logging_config import LOG_LEVEL
from irsol_data_pipeline.logging_config import setup_logging as _setup_base_logging


class PrefectLogLevel(enum.Enum):
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


_prefect_sink_added = False


def _extract_traceback_message(record: dict) -> str | None:
    """Extract a formatted traceback from a loguru record if present."""
    exception = record.get("exception")
    if exception is None:
        return None

    try:
        return "".join(
            traceback.format_exception(
                exception.type,
                exception.value,
                exception.traceback,
            ),
        ).strip()
    except Exception:
        return str(exception)


def _extract_loguru_level_from_prefect_log_level(level: PrefectLogLevel) -> LOG_LEVEL:
    """Map PrefectLogLevel to the loguru LOG_LEVEL used in the pipeline."""
    if level.value < PrefectLogLevel.DEBUG.value:
        return "TRACE"
    elif level.value < PrefectLogLevel.INFO.value:
        return "DEBUG"
    elif level.value < PrefectLogLevel.WARNING.value:
        return "INFO"
    elif level.value < PrefectLogLevel.ERROR.value:
        return "WARNING"
    elif level.value < PrefectLogLevel.CRITICAL.value:
        return "ERROR"
    else:
        return "CRITICAL"


def _extract_std_level_from_loguru_level(level: LOG_LEVEL) -> int:
    pass


def setup_logging(level: PrefectLogLevel):
    """Configure loguru logging with a Prefect sink that forwards logs to the
    run logger."""
    global _prefect_sink_added  # noqa PLW0603 - it's ok to handle globals in this case
    if _prefect_sink_added:
        return

    loguru_base_level = _extract_loguru_level_from_prefect_log_level(level)
    _setup_base_logging(level=loguru_base_level)

    std_base_level = _extract_std_level_from_loguru_level(loguru_base_level)

    try:
        run_logger = get_run_logger()
        run_logger.setLevel(std_base_level)
    except Exception:
        return  # Not inside a flow/task run context

    def _prefect_sink(message):
        record = message.record

        # loguru and stdlib share numeric levels (DEBUG=10, INFO=20, etc.)
        # Map loguru-only levels: TRACE(5)->DEBUG(10), SUCCESS(25)->INFO(20)
        SUCCESS_LEVEL = 25
        level_no = record["level"].no
        if level_no < stdlib_logging.DEBUG:
            level_no = stdlib_logging.DEBUG
        elif level_no == SUCCESS_LEVEL:
            level_no = stdlib_logging.INFO

        traceback_message = _extract_traceback_message(record)
        extra_message = ", ".join(
            f"{k}={v}" for k, v in record["extra"].items() if k != "_extra"
        )
        full_message = (
            (f"{record['message']} | {extra_message}")
            if extra_message
            else record["message"]
        )
        if traceback_message:
            full_message = f"{full_message}\n{traceback_message}"

        run_logger.log(level_no, full_message)

    logger.add(_prefect_sink, format="{message}", level="TRACE")
    _prefect_sink_added = True
