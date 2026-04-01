"""Centralized names and access helpers for Prefect Variables."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, cast

from loguru import logger
from prefect.variables import Variable

from irsol_data_pipeline.exceptions import DatasetRootNotConfiguredError


class PrefectVariableName(Enum):
    """Canonical Prefect Variable names used across flows and entrypoints."""

    DATA_ROOT_PATH = "data-root-path"
    JSOC_EMAIL = "jsoc-email"
    JSOC_DATA_DELAY_DAYS = "jsoc-data-delay-days"
    CACHE_EXPIRATION_HOURS = "cache-expiration-hours"
    FLOW_RUN_EXPIRATION_HOURS = "flow-run-expiration-hours"
    PIOMBO_BASE_PATH = "piombo-base-path"
    PIOMBO_HOSTNAME = "piombo-hostname"
    PIOMBO_USERNAME = "piombo-username"


def get_variable(name: PrefectVariableName, default: Any = None) -> Any:
    """Retrieve a Prefect Variable by name with logging.

    Args:
        name: The canonical variable name to look up.
        default: Value returned when the variable is not set in Prefect.

    Returns:
        The stored variable value, or ``default`` when not found.
    """
    not_found = cast("Any", object())
    with logger.contextualize(variable=name.value):
        value = Variable.get(name.value, default=not_found)
        if value is not_found:
            logger.warning(
                "Prefect Variable not set, using default",
                default=default,
            )
            value = default
        else:
            logger.info("Resolved Prefect Variable", value=value)
        return value


async def aget_variable(name: PrefectVariableName, default: Any = None) -> Any:
    """Asynchronously retrieve a Prefect Variable by name with logging.

    Args:
        name: The canonical variable name to look up.
        default: Value returned when the variable is not set in Prefect.

    Returns:
        The stored variable value, or ``default`` when not found.
    """
    with logger.contextualize(variable=name.value):
        not_found = cast("Any", object())
        value = await Variable.aget(name.value, default=not_found)
        if value is not_found:
            logger.warning(
                "Prefect Variable not set, using default",
                default=default,
            )
            value = default
        else:
            logger.info("Resolved Prefect Variable", value=value)
        return value


def resolve_dataset_roots(roots: tuple[str | Path, ...] | None = None) -> list[Path]:
    """Resolve one or more dataset roots from an explicit argument or Prefect
    Variable.

    The argument or Prefect Variable value may be a single path or a
    comma-separated list of paths (e.g. ``/srv/data1,/srv/data2``).

    Args:
        roots: Explicit dataset root path(s) override.

    Returns:
        List of resolved dataset root paths (at least one element).

    Raises:
        DatasetRootNotConfiguredError: If neither an argument nor a configured
            Prefect Variable is available, or if all provided paths are blank.
    """
    if roots:
        explicit_roots = [str(r).strip() for r in roots if str(r).strip()]
        if explicit_roots:
            logger.info(
                "Using explicit dataset root argument(s)",
                roots=explicit_roots,
                count=len(explicit_roots),
            )
            return [Path(r) for r in explicit_roots]

    raw = str(
        get_variable(PrefectVariableName.DATA_ROOT_PATH, default=""),
    ).strip()

    if not raw:
        raise DatasetRootNotConfiguredError(PrefectVariableName.DATA_ROOT_PATH.value)

    paths = [Path(p.strip()) for p in raw.split(",") if p.strip()]

    if not paths:
        raise DatasetRootNotConfiguredError(PrefectVariableName.DATA_ROOT_PATH.value)

    if len(paths) == 1:
        logger.info("Using single dataset root", root=str(paths[0]))
    else:
        logger.info(
            "Using multiple dataset roots",
            roots=[str(p) for p in paths],
            count=len(paths),
        )

    return paths
