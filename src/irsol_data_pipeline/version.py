"""Package version helpers."""

from __future__ import annotations

import importlib.metadata

_DISTRIBUTION_NAME = "irsol-data-pipeline"

try:
    __version__ = importlib.metadata.version(_DISTRIBUTION_NAME)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"
