"""Shared types used across the pipeline."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict


class StokesParameters(BaseModel):
    """The four Stokes parameters: I, Q, U, V."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    i: np.ndarray
    q: np.ndarray
    u: np.ndarray
    v: np.ndarray

    def __iter__(self):
        """Allow unpacking: i, q, u, v = stokes."""
        return iter((self.i, self.q, self.u, self.v))
