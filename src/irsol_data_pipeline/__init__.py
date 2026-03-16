"""IRSOL Solar Observation Data Processing Pipeline."""

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for matplotlib

from .version import __version__

__all__ = ["__version__"]
