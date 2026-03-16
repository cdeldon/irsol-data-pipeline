"""Reader for ZIMPOL .dat/.sav measurement files."""

from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
from scipy.io import readsav

from irsol_data_pipeline.core.models import (
    FlatField,
    Measurement,
    MeasurementMetadata,
    StokesParameters,
)


def read_zimpol_dat(
    file_path: Union[Path, str],
) -> tuple[StokesParameters, np.ndarray]:
    """Read a ZIMPOL .dat/.sav file and return Stokes parameters and raw info.

    Args:
        file_path: Path to the .dat or .sav file.

    Returns:
        Tuple of (StokesParameters, info_array).
    """
    path = Path(file_path).resolve()
    if path.suffix.lower() in [".dat", ".sav"]:
        data = readsav(str(path), verbose=False, python_dict=True)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    si = np.array(data["si"])
    sq = np.array(data["sq"])
    su = np.array(data["su"])
    sv = np.array(data["sv"])
    info = np.array(data["info"])

    # If data is 3D (no TCU averaging), average to 2D
    if si.ndim == 3:
        si = np.mean(si, axis=0)
    if sv.ndim == 3:
        sv = np.mean(sv, axis=0)

    return StokesParameters(i=si, q=sq, u=su, v=sv), info


def load_measurement(file_path: Union[Path, str]) -> Measurement:
    """Load a measurement from a .dat file.

    Args:
        file_path: Path to the .dat file.

    Returns:
        Measurement domain object.
    """
    path = Path(file_path)
    stokes, info = read_zimpol_dat(path)
    metadata = MeasurementMetadata.from_info_array(info)

    return Measurement(
        source_path=path,
        metadata=metadata,
        stokes=stokes,
    )


def load_flatfield(file_path: Union[Path, str]) -> FlatField:
    """Load a flat-field measurement from a .dat file.

    Args:
        file_path: Path to a flat-field .dat file (e.g. ff6302_m1.dat).

    Returns:
        FlatField domain object.
    """
    path = Path(file_path)
    stokes, info = read_zimpol_dat(path)
    metadata = MeasurementMetadata.from_info_array(info)

    return FlatField(
        source_path=path,
        metadata=metadata,
        stokes=stokes,
    )


def read_flatfield_si(file_path: Union[Path, str]) -> np.ndarray:
    """Read only the Stokes I from a flat-field file (for analysis).

    Returns the raw si array (may be 2D or 3D) without averaging,
    as the spectroflat analyzer needs the original shape.

    Args:
        file_path: Path to the flat-field .dat file.

    Returns:
        Raw Stokes I numpy array.
    """
    path = Path(file_path).resolve()
    data = readsav(str(path), verbose=False, python_dict=True)
    return np.array(data["si"])
