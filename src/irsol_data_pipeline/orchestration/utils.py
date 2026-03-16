import json
import string
from pathlib import Path
from typing import Callable

from irsol_data_pipeline.orchestration.decorators import prefect_enabled


def sanitize_artifact_title(title: str) -> str:
    """Sanitize a string to be used as a Prefect artifact title."""
    allowed_chars = string.ascii_lowercase + string.digits + "-"
    title = title.lower().replace("_", "-").replace("/", "-").replace(" ", "-")
    return "".join(c for c in title if c in allowed_chars)


def create_prefect_progress_callback(name: str, total: int) -> Callable[[int], None]:
    if prefect_enabled():
        from prefect.artifacts import create_progress_artifact, update_progress_artifact

        progress_id = create_progress_artifact(
            0.0,
            key=sanitize_artifact_title(f"progress-{name}"),
            description=f"Processing progress for {name}",
        )

        def update_progress(processed: int):
            percent = (processed + 1) / total * 100
            update_progress_artifact(artifact_id=progress_id, progress=percent)
    else:

        def update_progress(processed: int):
            pass  # No-op if not using Prefect

    return update_progress


def create_prefect_json_report(path: Path, title: str, key: str):
    if prefect_enabled():
        from prefect.artifacts import create_table_artifact

        with path.open() as f:
            content = json.load(f)

        table_rows = []
        for k, v in content.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    table_rows.append({"key": f"{k}.{kk}", "value": str(vv)})
            else:
                table_rows.append({"key": k, "value": str(v)})
        create_table_artifact(
            table=table_rows,
            key=sanitize_artifact_title(key),
            description=title,
        )
