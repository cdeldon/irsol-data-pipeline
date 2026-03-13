"""Writer for corrected measurement data."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Union

import numpy as np

from irsol_data_pipeline.core.models import StokesParameters


def write_corrected_dat(
    output_path: Union[Path, str],
    stokes: StokesParameters,
    info: np.ndarray,
) -> Path:
    """Write corrected Stokes data to a .dat file in numpy npz format.

    The output uses numpy's npz format with the same key names
    (si, sq, su, sv, info) so it can be loaded with consistent APIs.

    Args:
        output_path: Where to write the corrected data file.
        stokes: Corrected Stokes parameters.
        info: Original info metadata array.

    Returns:
        The path written to.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    np.savez(
        str(path),
        si=stokes.i,
        sq=stokes.q,
        su=stokes.u,
        sv=stokes.v,
        info=info,
    )
    return path


def save_correction_data(
    output_path: Union[Path, str],
    data: object,
) -> Path:
    """Persist correction data (e.g. FlatFieldCorrection) as pickle.

    Use this for objects that are not JSON-serializable (numpy arrays,
    spectroflat OffsetMap, etc.).

    Args:
        output_path: Where to write the pickle file.
        data: Object to persist.

    Returns:
        The path written to.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_correction_data(path: Union[Path, str]) -> object:
    """Load a pickled correction data file.

    Args:
        path: Path to the pickle file.

    Returns:
        Deserialized object.
    """
    with open(Path(path), "rb") as f:
        return pickle.load(f)  # noqa: S301 — trusted internal data
