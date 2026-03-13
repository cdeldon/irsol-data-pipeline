import pickle
from pathlib import Path
from typing import Union

from irsol_data_pipeline.core.models import FlatFieldCorrection


def read_flatfield_correction(output_path: Union[Path, str]) -> FlatFieldCorrection:
    """Reads the FlatFieldCorrection from a file using pickle."""
    path = Path(output_path)
    with open(path, "rb") as f:
        flatfield_correction = pickle.load(f)
    return flatfield_correction
