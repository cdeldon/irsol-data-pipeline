# Web Asset Compatibility

This document describes the web asset compatibility subsystem, which converts and deploys PNG visualization outputs to web-accessible formats on SFTP-based asset servers.

## Overview

The web asset compatibility system enables integration between the IRSOL data pipeline and web-based visualization platforms. It:

1. **Discovers** PNG outputs from processed measurements (profile plots and slit previews)
2. **Validates** which assets need deployment or update
3. **Converts** PNG images to JPEG format (configurable quality)
4. **Stages** converted assets in a temporary directory
5. **Deploys** JPEGs to a remote SFTP server (Piombo) for web consumption

The system is transport-agnostic via a protocol abstraction (`RemoteFileSystem`), allowing different deployment backends.

## Why This Layer Exists

This layer exists to replace the previous script-based deployment model (`quick-look` and
`image-generator` cron jobs) with a pipeline-native compatibility stage.

The science pipeline already generates local PNGs, but existing public systems consume deployed JPGs
at fixed legacy paths. This compatibility layer makes that translation explicit and reliable.

It is required to preserve backward compatibility with consumers that already expect:

1. `img_quicklook/{observation}/{measurement}.jpg` for quicklook previews.
2. `img_data/{observation}/{measurement}.jpg` for slit context images.
3. Public URLs that must resolve before SVO publication references thumbnail URLs.

In short, this is not an optional export helper: it is a contract-preserving migration layer.

## Architecture

### Core Domain Layer

**Module:** `core.web_asset_compatibility`

The core layer contains the domain models and business logic:

```
src/irsol_data_pipeline/core/web_asset_compatibility/
├── models.py       # Domain types: WebAssetKind, WebAssetFolderName, WebAssetSource
├── discovery.py    # Scan measurement outputs to discover PNG assets
└── conversion.py   # PNG → JPEG conversion via Pillow
```

#### Models

**`WebAssetKind`** (enum):
- `quicklook` — Corrected Stokes profile visualization
- `context` — Slit geometry context image (SDO overlay)

**`WebAssetFolderName`** (enum):
- `img_quicklook` — Legacy folder for quicklook assets
- `img_data` — Legacy folder for context assets

**`WebAssetSource`** (immutable Pydantic model):
Represents a single PNG-to-JPEG mapping for a measurement:

```python
class WebAssetSource(BaseModel):
    measurement_name: str          # e.g., "6302_m1"
    observation_day: date
    kind: WebAssetKind
    source_png_path: Path          # Input PNG
    target_jpg_filename: str       # Output JPEG filename
```

#### Discovery

**Function:** `discover_web_assets_for_day(day: ObservationDay) -> list[WebAssetSource]`

Scans the `processed/` folder for PNG outputs and builds asset source mappings:

- Matches `*_profile_corrected.png` → `quicklook` JPG targets
- Matches `*_slit_preview.png` → `context` JPG targets
- Returns sorted list indexed by measurement and asset kind

#### Conversion

**Function:** `convert_png_to_jpeg(source: Path, target: Path, quality: int = 85) -> None`

Validates quality level (1–95) and converts PNG to JPEG using Pillow:

```python
result = Image.open(source).convert("RGB")
result.save(target, format="JPEG", quality=quality, optimize=True)
```

### Pipeline Layer

**Module:** `pipeline.web_asset_compatibility`

Orchestration and state management:

```python
def plan_web_assets_for_day(
    day: ObservationDay,
    overwrite_existing: bool = False,
) -> DayWebAssetPlan:
    """Plan assets for a single day, checking remote inventories."""

def stage_and_upload_assets(
    plan: DayWebAssetPlan,
    remote_fs: RemoteFileSystem,
    jpeg_quality: int = 85,
) -> WebAssetUploadResult:
    """Convert PNGs, stage JPEGs, upload to remote server."""
```

**`DayWebAssetPlan`** (immutable):
- `day: ObservationDay`
- `assets_to_upload: list[WebAssetSource]`
- `assets_already_exist: list[WebAssetSource]` (skipped unless `overwrite_existing`)
- `missing_png_sources: list[str]` (PNG not found locally)

**`WebAssetUploadResult`** (immutable):
- `uploaded_count: int`
- `skipped_count: int`
- `failed_assets: list[tuple[WebAssetSource, str]]` (asset, error message)

### Remote File System Protocol

**Module:** `core.remote_filesystem`

Transport-agnostic abstraction for remote file operations:

```python
class RemoteFileSystem(Protocol):
    """Protocol for remote file system operations (SFTP, S3, etc.)."""

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        """Upload a file from local storage to remote location."""

    def list_files(self, remote_dir: str) -> list[str]:
        """List all files in a remote directory."""

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the remote server."""

    def delete_file(self, remote_path: str) -> None:
        """Delete a file from the remote server."""
```

### Integration Layer

**Module:** `integrations.piombo`

Concrete implementation for Piombo SFTP deployment:

```python
class SftpRemoteFileSystem(RemoteFileSystem):
    """SFTP adapter for Piombo web asset deployment."""

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        base_path: str = "/web/assets/zimpol",
    ):
        ...

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        # Use Paramiko to upload via SFTP
        ...
```

Configuration is read from Prefect Variables:
- `piombo-hostname` — SFTP server
- `piombo-username` — Login username
- `piombo-password` — Login password (securely stored)
- `piombo-base-path` — Base path on server (e.g., `/irsol_db/docs/web-site/assets`)

## Workflows

### Full Scan (web-assets-compatibility-full)

Prefect flow: `publish_web_assets_for_root()`

1. Query Prefect Variables to resolve dataset root and Piombo credentials
2. Scan dataset for all observation days
3. For each day:
   a. Discover PNG assets
   b. Plan SFTPupload (check remote inventory)
   c. Convert PNGs → JPEGs (parallel tasks)
   d. Upload JPEGs to Piombo and log results
4. Aggregate results and report summary

### Daily Trigger (web-assets-compatibility-daily)

Prefect flow: `publish_web_assets_for_day(day_path: str)`

1. Construct `ObservationDay` from the provided path argument
2. Discover PNG assets for the day
3. Plan assets for upload (optionally overwriting existing)
4. Convert and stage JPEGs in a temporary directory
5. Upload to Piombo SFTP server
6. Log success/failure per asset

## Configuration & Deployment

### Prefect Variables

| Variable | Type | Required | Example |
|----------|------|----------|---------|
| `piombo-hostname` | str | Yes | `piombo.example.com` |
| `piombo-username` | str | Yes | `web-deploy-user` |
| `piombo-password` | str | Yes | (securely stored in Prefect) |
| `piombo-base-path` | str | No | `/irsol_db/docs/web-site/assets` |
| `data-root-path` | str | Yes | `/data/observations` |

### Scheduling

The flow deployment is registered in `cli.metadata`:

```python
METADATA.register_flow_group(
    name="web-assets-compatibility",
    flows=[
        publish_web_assets_for_root,
        publish_web_assets_for_day,
    ],
    tags=["web-assets-compatibility"],
)
```

Schedule the `web-assets-compatibility-full` to run daily after other pipelines complete.

## Error Handling

- **Missing PNG sources** — Logged as warnings, measurement skipped, pipeline continues
- **Conversion failures** — PNG malformed or incompatible; error recorded per asset
- **SFTP upload failures** — Network error, authentication, or permissions; failure logged with retry logic
- **Validation errors** — Invalid Prefect variables or missing required config; flow fails fast

All errors are recorded in `WebAssetUploadResult.failed_assets` and reported to the user.

## Testing

Tests are located in:

```
tests/unit/irsol_data_pipeline/core/web_asset_compatibility/
├── test_models.py       # Domain model validation
├── test_discovery.py    # PNG asset discovery
└── test_conversion.py   # PNG → JPEG conversion

tests/unit/irsol_data_pipeline/pipeline/
└── test_web_asset_compatibility.py  # Planning and staging logic

tests/unit/irsol_data_pipeline/integrations/
└── test_piombo.py       # SFTP adapter integration tests
```

Test patterns:
- Mock the `RemoteFileSystem` protocol for unit tests
- Construct test PNG files in-memory via Pillow (do not use real .dat files)
- Validate that discovered assets match expected naming conventions
- Verify proper error handling when PNGs are missing or malformed

## Related Documentation

- [Architecture Overview](../overview/architecture.md) — high-level system design
- [Pipeline Overview](../pipeline/pipeline_overview.md) — processing stages
- [Prefect Integration](../pipeline/prefect_integration.md) — orchestration and flows
- [CLI Usage](../cli/cli_usage.md) — user-facing web asset commands
