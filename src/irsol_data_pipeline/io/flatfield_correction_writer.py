import pickle
from pathlib import Path
from typing import Union

from irsol_data_pipeline.core.models import FlatFieldCorrection


def write_flatfield_correction(
    flatfield_correction: FlatFieldCorrection, output_path: Union[Path, str]
) -> None:
    """Save the FlatFieldCorrection to a file using pickle."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(flatfield_correction, f)
