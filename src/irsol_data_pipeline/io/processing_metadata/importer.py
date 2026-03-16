import json
from pathlib import Path
from typing import Any


def read_metadata(path: Path) -> dict[str, Any]:
    """Read a metadata or error JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed dict.
    """
    with path.open() as f:
        return json.load(f)
