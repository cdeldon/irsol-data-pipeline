# IRSOL Data Pipeline


## Table of Contents

1. [What This Repository Does](#1-what-this-repository-does)
2. [Key Concepts and Terminology](#2-key-concepts-and-terminology)
3. [Repository Layout](#3-repository-layout)
4. [Installation](#4-installation)
5. [Pipeline A — Flat-Field Correction](#5-pipeline-a--flat-field-correction)
6. [Pipeline B — Slit Image Generation](#6-pipeline-b--slit-image-generation)
7. [Running the Pipelines](#7-running-the-pipelines)
   - [Quick start: process a single measurement](#71-quick-start-process-a-single-measurement)
   - [Quick start: generate a slit preview image](#72-quick-start-generate-a-slit-preview-image)
   - [Visualising a processed FITS file](#73-visualising-a-processed-fits-file)
   - [Running locally (without Prefect)](#74-running-locally-without-prefect)
   - [Running with Prefect](#75-running-with-prefect)
8. [Using the Pipelines as a Python Library](#8-using-the-pipelines-as-a-python-library)
9. [Managing Prefect Deployments in Production](#9-managing-prefect-deployments-in-production)
10. [Extending the System](#10-extending-the-system)
11. [Configuration Reference](#11-configuration-reference)
12. [Testing](#12-testing)


## 1. What This Repository Does

This repository hosts the **IRSOL data pipeline** — a collection of automated processing pipelines for solar spectro-polarimetric measurements captured at the IRSOL observatory (Locarno, Switzerland). Each pipeline addresses a different aspect of the data processing workflow and can be run independently or together.

### Pipelines at a glance

| Pipeline | Purpose | Schedule |
|---|---|---|
| **Flat-Field Correction** | Removes dust artefacts, corrects smile distortion, calibrates wavelength axis → produces science-ready FITS files | Daily at 01:00 |
| **Slit Image Generation** | Generates 6-panel SDO context images showing the spectrograph slit position on the solar disc | Daily at 02:00 |
| **Maintenance** | Cleans up old Prefect flow run history | Daily at 00:00 |

### Pipeline A — Flat-Field Correction

Raw measurements from the ZIMPOL instrument contain optical artefacts that need to be corrected before the data is scientifically useful:

1. **Dust artefacts** — particles on the sensor create intensity patterns unrelated to the sun.
2. **Smile distortion** — spectral lines appear curved rather than straight due to optical aberrations.
3. **Unknown wavelength scale** — pixel positions must be mapped to physical wavelengths (Ångström) using a calibration procedure.

This pipeline corrects all three issues automatically, turning reduced `.dat` files into calibrated FITS files ready for scientific analysis.

> For every reduced measurement in the dataset, the pipeline finds the best matching flat-field, applies flat-field and smile correction, calibrates the wavelength axis, and writes a corrected FITS file with metadata.

### Pipeline B — Slit Image Generation

Each observation records where the spectrograph slit was pointed on the solar disc. This pipeline:

1. Reads slit coordinates and derotator angles from the measurement metadata.
2. Fetches SDO/AIA (UV + EUV) and SDO/HMI (continuum + magnetogram) images from the JSOC archive for the same time window.
3. Renders a 6-panel preview image with the slit position, μ value, +Q polarization direction, and solar limb overlaid on each SDO image.

> For every reduced measurement, the pipeline generates a `*_slit_preview.png` image showing the slit position in spatial context on the solar disc.

### High-level system diagram

```mermaid
graph TB
    subgraph inputs["Inputs"]
        DAT["ZIMPOL .dat files
		(reduced measurements
		+ flat-fields)
		"]
    end

    subgraph pipeline_a["Pipeline A: Flat-Field Correction"]
        direction TB
        SCAN_A["Dataset Scanner"]
        FF["Flat-Field Analysis
		(spectroflat)"]
        CORR["Flat-Field Correction
		+ Smile Correction"]
        CAL["Wavelength
		Auto-Calibration"]
        IO_A["Output Writer"]
    end

    subgraph pipeline_b["Pipeline B: Slit Image Generation"]
        direction TB
        SCAN_B["Dataset Scanner"]
        COORD["Slit Coordinate\nTransformation"]
        SDO["SDO Data Fetch\n(DRMS/JSOC)"]
        RENDER["6-Panel Renderer"]
    end

    subgraph outputs["Outputs"]
        FITS["*_corrected.fits\nStokes I, Q, U, V + headers"]
        META["*_metadata.json\nProcessing summary"]
        PNG_PROF["*_profile_*.png\nStokes profile images"]
        PKL["*_flat_field_correction_data.pkl\nCorrection payload"]
        PNG_SLIT["*_slit_preview.png\nSDO context images"]
    end

    subgraph orchestration["Orchestration (Prefect)"]
        SCHED_A["Flat-field: daily at 01:00"]
        SCHED_B["Slit images: daily at 02:00"]
        UI["Web UI\nlocalhost:4200"]
    end

    DAT --> SCAN_A
    SCAN_A --> FF --> CORR --> CAL --> IO_A
    IO_A --> FITS
    IO_A --> META
    IO_A --> PNG_PROF
    IO_A --> PKL

    DAT --> SCAN_B
    SCAN_B --> COORD --> SDO --> RENDER
    RENDER --> PNG_SLIT

    SCHED_A --> SCAN_A
    SCHED_B --> SCAN_B
    UI --> SCHED_A
    UI --> SCHED_B
```


## 2. Key Concepts and Terminology

Before diving into code, here is a glossary of domain terms used throughout the codebase:

| Term | What it means |
|---|---|
| **Stokes parameters (I, Q, U, V)** | Four numbers that fully describe the polarisation state of light. `I` is total intensity; `Q`, `U`, `V` describe linear and circular polarisation. Each is a 2D array `(n_spatial_pixels × n_wavelength_pixels)`. |
| **Flat-field (`.dat` file starting with `ff`)** | A calibration exposure taken of a uniform light source. It encodes the spatially-varying sensitivity of the sensor (dust artefacts) and the spectral-line curvature (smile). |
| **Flat-field correction** | Dividing each measurement by the flat-field to remove dust patterns, then geometrically unwarping spectral lines to straighten them. |
| **Smile distortion** | The bending of spectral lines across the spatial axis caused by optical misalignment. Corrected using the `spectroflat` library. |
| **Wavelength calibration** | The process of assigning a physical wavelength (in Ångström) to each pixel column. The pipeline does this automatically by cross-correlating the measured spectrum against bundled reference solar spectra. |
| **`max_delta`** | The maximum allowed time difference between a measurement and the flat-field used to correct it. If no flat-field is available within this window, processing fails with an error. Default: 2 hours. |
| **Observation day** | A directory under `<root>/<year>/<day>/` that contains subdirectories `raw/`, `reduced/`, and `processed/`. |
| **`reduced/`** | Directory containing raw `.dat` measurement and flat-field files from the instrument. |
| **`processed/`** | Directory where the pipeline writes all output files. |
| **FITS** | A standard astronomical data format. |
| **SDO** | Solar Dynamics Observatory — a NASA spacecraft that continuously images the Sun. |
| **AIA** | Atmospheric Imaging Assembly — an SDO instrument that takes UV and EUV images of the Sun. |
| **HMI** | Helioseismic and Magnetic Imager — an SDO instrument that measures continuum intensity and magnetic fields. |
| **DRMS/JSOC** | Data Record Management System at the Joint Science Operations Center — the archive from which SDO images are downloaded. |
| **Slit preview** | A 6-panel image showing the spectrograph slit position overlaid on AIA and HMI images, providing spatial context for each observation. |
| **μ (mu)** | Cosine of the heliocentric angle — 1.0 at disc center, 0.0 at the limb. Indicates how much limb darkening affects the measurement. |
| **Derotator** | An optical element that compensates for field rotation. Its angle and coordinate system determine slit orientation on the solar disc. |


## 3. Repository Layout

```text
irsol-data-pipeline/
├── data/                          # Local dataset root for development and testing
├── documentation/                 # Extra documentation assets (screenshots, notes)
├── entrypoints/                   # Thin executable scripts (CLI and deployment bootstrap)
│   ├── serve_flat_field_correction_pipeline.py   # Start Prefect flat-field correction deployments
│   ├── serve_slit_image_pipeline.py              # Start Prefect slit image generation deployments
│   ├── serve_prefect_maintenance.py              # Start Prefect maintenance deployment
│   ├── process_single_measurement.py             # Process one .dat file from a terminal
│   └── plot_fits_profile.py                      # Visualise a processed FITS file
│
├── src/irsol_data_pipeline/
│   ├── core/                      # Domain models, correction, calibration, slit-image primitives
│   │   ├── models.py              # Shared Pydantic data models
│   │   ├── config.py              # Shared constants, defaults, and environment variables
│   │   ├── correction/
│   │   │   ├── analyzer.py        # Analyse a flat-field → produces correction artefacts
│   │   │   └── corrector.py       # Apply the correction to a measurement
│   │   ├── calibration/
│   │   │   ├── autocalibrate.py   # Wavelength calibration logic
│   │   │   └── refdata/           # Bundled reference solar spectra (.npy files)
│   │   └── slit_images/
│   │       ├── config.py          # Observatory location, telescope specs, SDO query params
│   │       ├── coordinates.py     # Slit geometry: Earth→Solar frame, mu, endpoints
│   │       ├── solar_data.py      # Fetch SDO/AIA and SDO/HMI images via DRMS
│   │       ├── renderer.py        # 6-panel slit-preview rendering logic
│   │       └── z3readbd.py        # ZIMPOL3 binary header reader (for limbguider data)
│   │
│   ├── io/                        # File reading and writing — no science logic
│   │   ├── dat/
│   │   │   └── importer.py        # Read .dat/.sav → StokesParameters + info array
│   │   ├── fits/
│   │   │   ├── exporter.py        # Write StokesParameters → .fits
│   │   │   └── importer.py        # Read .fits → StokesParameters + CalibrationResult
│   │   ├── flatfield/
│   │   │   ├── exporter.py        # Serialise FlatFieldCorrection to .pkl
│   │   │   └── importer.py        # Load FlatFieldCorrection from .pkl
│   │   └── processing_metadata/
│   │       ├── exporter.py        # Write *_metadata.json and *_error.json
│   │       └── importer.py        # Read metadata and error JSON files
│   │
│   ├── pipeline/                  # High-level processing logic, still usable without Prefect
│   │   ├── filesystem.py          # Dataset discovery + canonical path helpers
│   │   ├── scanner.py             # Find observation days with pending measurements
│   │   ├── flatfield_cache.py     # Build and query the flat-field correction cache
│   │   ├── day_processor.py       # Process all measurements in one observation day
│   │   ├── measurement_processor.py  # Process a single measurement end-to-end
│   │   └── slit_images_processor.py  # Orchestrate slit preview generation for measurements/days
│   │
│   ├── orchestration/             # Prefect-specific wiring (flows, decorators, logging)
│   │   ├── decorators.py          # Conditional @task/@flow (no-ops without PREFECT_ENABLED)
│   │   ├── patch_logging.py       # Forward loguru logs to Prefect's run logger
│   │   ├── retry.py               # Retry helper for Prefect tasks
│   │   ├── utils.py               # Prefect artifact helpers
│   │   └── flows/
│   │       ├── flat_field_correction.py   # Flat-field correction flows
│   │       ├── slit_image_generation.py   # Slit image generation flows
│   │       └── delete_old_prefect_data.py # Maintenance flow
│   │
│   ├── plotting/
│   │   ├── profile.py             # Matplotlib Stokes profile plots
│   │   └── slit.py                # Slit preview plotting wrapper
│   ├── exceptions.py              # All custom exception types
│   ├── logging_config.py          # Loguru configuration
│   └── version.py                 # Package version string
│
├── tests/unit/                    # Pytest unit tests
├── pyproject.toml
├── Makefile
└── README.md
```

### Layered architecture

The codebase is deliberately split into independent layers — you can use lower layers without knowing anything about higher ones:

```mermaid
graph TB
    A["<b>core</b>
	Domain models and reusable logic
	(correction, calibration, slit geometry, SDO fetch)"]
    B["<b>io</b>
	File reading and writing
	(dat, fits, flatfield, metadata)"]
    C["<b>pipeline</b>
	High-level processing steps
	(scan, build cache, process day/measurement, slit previews)"]
    C2["<b>plotting</b>
	Matplotlib output helpers
	(Stokes profiles, slit previews)"]
    D["<b>orchestration</b>
	Prefect flows and scheduling"]
    E["<b>entrypoints</b>
	CLI scripts"]

    A --> B
    A --> C
    B --> C
    A --> C2
    C --> D
    D --> E
```

> **Key design rule**: Only `orchestration/` is Prefect-specific.
> The rest of the package, including slit-image generation code split across `core/`, `pipeline/`, and `plotting/`, remains importable and callable as plain Python.


## 4. Installation

### Prerequisites

- Python ≥ 3.10
- [`uv`](https://github.com/astral-sh/uv) package manager

Install `uv` if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Set up the environment

```bash
# Clone the repository (if not already done)
git clone <repo-url>
cd irsol-data-pipeline

# Create a virtual environment and install all dependencies
uv sync
```

All commands in this guide use `uv run <script>` which automatically activates the virtual environment.

### Available Make targets

```bash
make help                                      # List all targets
make lint                                      # Run pre-commit checks
make test                                      # Run tests with coverage
make prefect/dashboard                         # Start the Prefect server + dashboard
make prefect/serve-flat-field-correction-pipeline  # Serve the flat-field correction deployments
make prefect/serve-slit-image-pipeline         # Serve the slit image generation deployments
make prefect/serve-maintenance-pipeline        # Serve the maintenance deployment
make prefect/reset                             # Reset the local Prefect database
make clean                                     # Remove __pycache__ and .pyc files
```


## 5. Pipeline A — Flat-Field Correction

This section explains exactly what happens when a measurement is processed by the flat-field correction pipeline.

### Dataset layout

The pipeline expects data organised like this:

```text
<root>/
└── 2025/
    └── 20250312/            ← observation day
        ├── raw/             ← raw camera files (not read by this pipeline)
        ├── reduced/         ← input files for this pipeline
        │   ├── 6302_m1.dat  ← measurement (wavelength 6302 Å, measurement id 1)
        │   ├── 6302_m2.dat
        │   ├── ff6302_m1.dat ← flat-field for wavelength 6302 Å
        │   └── ff6302_m2.dat
        └── processed/       ← output directory (created automatically)
```

**File naming conventions in `reduced/`:**
- Measurements: `<wavelength>_m<id>.dat` — e.g. `6302_m1.dat`
- Flat-fields: `ff<wavelength>_m<id>.dat` — e.g. `ff6302_m1.dat`
- Files starting with `cal` or `dark` are silently ignored.

### Step-by-step walkthrough

The pipeline runs through these stages for every observation day that has unprocessed measurements:

```mermaid
flowchart TD
    A["<b>1. Dataset Scan</b>
	Walk root/<year>/<day>/ directories
	Find days with pending measurements"] --> B

    B["<b>2. Flat-Field Cache</b>
	For each ff*.dat in reduced/:
	  • Load Stokes I
	  • Run spectroflat analysis
	  • Store dust_flat + offset_map
	Cache persisted to processed/_cache/*.pkl"] --> C

    C["<b>3. For each measurement</b>
	Load <wavelength>_m<id>.dat"] --> D

    D{"Already processed?
	processed/ has
	*_corrected.fits or
	*_error.json"} -->|Yes| E["Skip — log and continue"]
    D -->|No| F

    F["<b>4. Find best flat-field</b>
	Match by wavelength
	Select closest timestamp
	within max_delta (default: 2h)"] --> G

    G{"Match found?"} -->|No| H["Write *_error.json
	and continue"]
    G -->|Yes| I

    I["<b>5. Apply correction</b>
	Divide Stokes I by dust_flat
	Apply smile correction to I, Q, U, V"] --> J

    J["<b>6. Wavelength calibration</b>
	Cross-correlate with reference spectrum
	Fit spectral line positions
	Output: a0 (offset Å) + a1 (scale Å/px)"] --> K

    K["<b>7. Write outputs</b>
	*_corrected.fits
	*_flat_field_correction_data.pkl
	*_metadata.json
	*_profile_corrected.png
	*_profile_original.png"]
```

### Output files

For a source file `6302_m1.dat`, the pipeline produces inside `processed/`:

| File | Description |
|---|---|
| `6302_m1_corrected.fits` | Multi-extension FITS with four Stokes images (I, Q/I, U/I, V/I) and calibration headers |
| `6302_m1_flat_field_correction_data.pkl` | Serialised `FlatFieldCorrection` — can be reloaded to inspect or reapply the correction |
| `6302_m1_metadata.json` | Processing summary: timestamps, flat-field used, calibration values |
| `6302_m1_profile_corrected.png` | Plot of all four Stokes components after correction |
| `6302_m1_profile_original.png` | Plot of all four Stokes components before correction |
| `6302_m1_error.json` | Written **only** if processing fails — contains the error message |

Flat-field analysis cache files are stored separately under `processed/_cache/`:

| File | Description |
|---|---|
| `ff6302_m1_correction_cache.pkl` | Cached `FlatFieldCorrection` — reused across pipeline runs to avoid re-analysing flat-fields |

### Idempotency

The pipeline is **idempotent**: re-running it on a day that already has `*_corrected.fits` or `*_error.json` files will simply skip those measurements. To re-process a measurement, delete its output files from `processed/`.


## 6. Pipeline B — Slit Image Generation

This section explains what happens when slit preview images are generated.

### What it produces

For each measurement `6302_m1.dat`, the pipeline generates:

| File | Description |
|---|---|
| `6302_m1_slit_preview.png` | 6-panel image: AIA 1600, AIA 131, AIA 193, AIA 304, HMI Continuum, HMI Magnetogram — each with the slit position overlay |
| `6302_m1_slit_preview_error.json` | Written **only** if generation fails — contains the error message |

Downloaded SDO FITS files are cached under `processed/_sdo_cache/` and reused on subsequent runs.

### Step-by-step walkthrough

```mermaid
flowchart TD
    A["<b>1. Dataset Scan</b>
	Walk root/<year>/<day>/ directories
	List all observation days"] --> B

    B["<b>2. For each measurement</b>
	Load <wavelength>_m<id>.dat
	Parse metadata (coordinates, derotator, timestamps)"] --> C

    C{"Already has
	*_slit_preview.png or
	*_slit_preview_error.json?"} -->|Yes| D["Skip — log and continue"]
    C -->|No| E

    E["<b>3. Compute slit geometry</b>
	Read SDC_X, SDC_Y from metadata
	(or limbguider coordinates if enabled)
	Rotate Earth → Solar frame using P0 angle
	Compute slit endpoints and μ value"] --> F

    F["<b>4. Fetch SDO images</b>
	Query JSOC/DRMS for:
	  AIA 1600, 131, 193, 304
	  HMI continuum, magnetogram
	Select closest image to observation midpoint
	Download FITS files (cached)"] --> G

    G{"SDO data
	available?"} -->|No| H["Write *_slit_preview_error.json
	and continue"]
    G -->|Yes| I

    I["<b>5. Render 6-panel image</b>
	Crop each SDO image to FOV around slit
	Draw slit, +Q direction, μ circle, limb
	Add time labels and disclaimers"] --> J

    J["<b>6. Write output</b>
	*_slit_preview.png"]
```

### Coordinate transformation

The pipeline converts slit coordinates from the instrument frame to the solar frame:

1. **SDC coordinates** (`SDC_X`, `SDC_Y`) give the slit center in arcsec from disc center in the Earth's reference frame.
2. The **Sun P0 angle** is used to rotate these coordinates into the solar reference frame.
3. The **derotator angle** and **coordinate system** (equatorial or heliographic) determine the slit orientation.
4. **Limbguider coordinates** (`LG_CXM`, `LG_CYM`) can optionally replace SDC coordinates for higher accuracy — these are read from the original `.z3bd` raw file if available.

### Telescope support

The pipeline supports per-telescope slit dimensions:

| Telescope | Slit half-length (arcsec) | Slit width |
|---|---|---|
| IRSOL (Gregory) | 91.0 | `slit_setting × 7.9` arcsec |
| GREGOR | 22.0 | 0.25 arcsec (fixed) |

### Idempotency

Like the flat-field correction pipeline, slit image generation is **idempotent**: existing `*_slit_preview.png` or `*_slit_preview_error.json` files cause the measurement to be skipped. Delete these files to regenerate.

### Environment requirements

The `JSOC_EMAIL` environment variable must be set to a valid email address registered with [JSOC](http://jsoc.stanford.edu/). Without it, the pipeline cannot query for SDO data. Set it before running:

```bash
export JSOC_EMAIL="your.email@example.com"
```


## 7. Running the Pipelines

### 7.1 Quick start: process a single measurement

The fastest way to try the flat-field correction pipeline without setting up Prefect:

```bash
uv run entrypoints/process_single_measurement.py /path/to/reduced/6302_m1.dat
```

With explicit options:

```bash
uv run entrypoints/process_single_measurement.py /path/to/reduced/6302_m1.dat \
    --flatfield-dir /path/to/reduced \   # default: same directory as the measurement
    --output-dir    /path/to/processed \ # default: ../processed relative to reduced/
    --max-delta-hours 2.0 \              # default: 2.0
    --verbose                            # enable DEBUG logs
```

This script does not need a running Prefect server. It runs the full correction and calibration locally and writes all output files to `--output-dir`.

### 7.2 Quick start: generate a slit preview image

Generate a slit preview image for a single measurement without Prefect:

```python
from pathlib import Path
from irsol_data_pipeline.pipeline.slit_images_processor import generate_slit_image

generate_slit_image(
    measurement_path=Path("/path/to/reduced/6302_m1.dat"),
    processed_dir=Path("/path/to/processed"),
    jsoc_email="your.email@example.com",
)
```

This reads the measurement metadata, fetches SDO images from JSOC, renders the 6-panel preview, and saves `6302_m1_slit_preview.png` to the processed directory.

### 7.3 Visualising a processed FITS file

After processing, generate a Stokes profile plot from any `*_corrected.fits` file:

```bash
uv run entrypoints/plot_fits_profile.py /path/to/processed/6302_m1_corrected.fits
```

Save the plot to a custom path:

```bash
uv run entrypoints/plot_fits_profile.py /path/to/6302_m1_corrected.fits \
    --output /path/to/my_plot.png
```

The plot shows all four Stokes components (I, Q/I, U/I, V/I) as 2D images. When wavelength calibration is available in the FITS headers, the x-axis shows wavelengths in Ångström instead of pixel numbers.

### 7.4 Running locally (without Prefect)

You can drive the full scan-and-process loop directly from Python without any Prefect server.

#### Flat-field correction

```python
from pathlib import Path
from irsol_data_pipeline.pipeline.scanner import scan_dataset
from irsol_data_pipeline.pipeline.day_processor import process_observation_day

root = Path("/path/to/data")

# Find all observation days with pending measurements
scan_result = scan_dataset(root)
print(f"Days with pending work: {list(scan_result.pending_measurements.keys())}")

# Process each day
for day in scan_result.observation_days:
    if day.name in scan_result.pending_measurements:
        result = process_observation_day(day)
        print(f"{day.name}: processed={result.processed}, failed={result.failed}")
```

#### Slit image generation

```python
from pathlib import Path
from irsol_data_pipeline.pipeline.filesystem import discover_observation_days
from irsol_data_pipeline.pipeline.slit_images_processor import generate_slit_images_for_day

root = Path("/path/to/data")
days = discover_observation_days(root)

for day in days:
    result = generate_slit_images_for_day(day, jsoc_email="your.email@example.com")
    print(f"{day.name}: generated={result.processed}, skipped={result.skipped}, failed={result.failed}")
```

### 7.5 Running with Prefect

Prefect adds scheduling, a web UI, task retries, and structured logging.

**Step 1 — Start the Prefect server in one terminal:**

```bash
make prefect/dashboard
# Server starts at http://127.0.0.1:4200
```

**Step 2 — Serve the processing deployments in a second terminal:**

```bash
make prefect/serve-flat-field-correction-pipeline
```

This registers two deployments and keeps the process running as a worker:

| Deployment | Schedule | What it does |
|---|---|---|
| `run-flat-field-correction-pipeline` | Daily at 01:00 | Scans the whole dataset and processes all pending measurements |
| `run-daily-flat-field-correction-pipeline` | On demand | Processes a single observation day directory |

**Step 3 — Serve the slit image generation deployments in a third terminal:**

```bash
JSOC_EMAIL="your.email@example.com" make prefect/serve-slit-image-pipeline
```

| Deployment | Schedule | What it does |
|---|---|---|
| `run-slit-image-pipeline` | Daily at 02:00 | Generates slit preview images for all observation days |
| `run-daily-slit-image-pipeline` | On demand | Generates slit previews for a single observation day |

**Step 4 — Serve the maintenance deployment in a fourth terminal:**

```bash
make prefect/serve-maintenance-pipeline
```

| Deployment | Schedule | What it does |
|---|---|---|
| `delete-old-prefect-flow-runs` | Daily at 00:00 | Deletes Prefect run history older than 4 weeks |

**Step 5 — Trigger a run manually or wait for the schedule:**

1. Open `http://127.0.0.1:4200` in your browser.
2. Click **Deployments** in the left sidebar.
3. Select `run-flat-field-correction-pipeline`.
4. Click **Run → Quick Run** (uses default parameters) or **Run → Custom Run** to override:
   - `root`: dataset root path (default: `<repo>/data`)
   - `max_delta_hours`: maximum flat-field time gap in hours (default: `2.0`)
   - `max_concurrent_days_to_process`: parallelism cap (default: `CPU count − 1`, max 12)

![Prefect dashboard showing deployment and run logs](./documentation/assets/prefect-dashboard.png)

**The `PREFECT_ENABLED` environment variable:**

The `@task` and `@flow` decorators in this codebase are conditional. When `PREFECT_ENABLED=true` is set (done automatically by `make prefect/serve-*`), they act like real Prefect decorators. Otherwise, they are transparent no-ops — meaning the same pipeline code runs perfectly fine without Prefect installed or running. This is what makes the library-style usage in Section 7.4 work.


## 8. Using the Pipelines as a Python Library

Because the scientific logic is isolated from the orchestration layer, every module can be imported and called independently.

### Reading a `.dat` file

```python
from pathlib import Path
from irsol_data_pipeline.io import dat as dat_io
from irsol_data_pipeline.core.models import MeasurementMetadata

stokes, info = dat_io.read(Path("6302_m1.dat"))

# stokes.i, stokes.q, stokes.u, stokes.v are 2D numpy arrays
print("Stokes I shape:", stokes.i.shape)   # e.g. (512, 1024)

# Parse the raw info array into a structured metadata object
metadata = MeasurementMetadata.from_info_array(info)
print("Wavelength:", metadata.wavelength)          # e.g. 6302
print("Observation start:", metadata.datetime_start)
```

### Analysing a flat-field

```python
import numpy as np
from irsol_data_pipeline.io import dat as dat_io
from irsol_data_pipeline.core.correction.analyzer import analyze_flatfield

stokes, info = dat_io.read("ff6302_m1.dat")

# Returns (dust_flat, offset_map, desmiled)
dust_flat, offset_map, desmiled = analyze_flatfield(stokes.i)
```

### Applying flat-field correction

```python
from irsol_data_pipeline.core.correction.corrector import apply_correction

corrected_stokes = apply_correction(
    stokes=measurement_stokes,
    dust_flat=dust_flat,
    offset_map=offset_map,
)
```

### Running wavelength calibration

```python
from irsol_data_pipeline.core.calibration.autocalibrate import calibrate_measurement

calibration = calibrate_measurement(corrected_stokes)

print(f"Pixel scale:       {calibration.pixel_scale:.4f} Å/px")
print(f"Wavelength offset: {calibration.wavelength_offset:.2f} Å")
print(f"Reference file:    {calibration.reference_file}")

# Convert pixel to wavelength
pixel = 256
wavelength = calibration.pixel_to_wavelength(pixel)
print(f"Pixel {pixel} → {wavelength:.2f} Å")
```

### Reading and writing FITS files

```python
from irsol_data_pipeline.io.fits.exporter import write_stokes_fits
from irsol_data_pipeline.io.fits.importer import load_fits_measurement
from pathlib import Path

# Write
output = Path("6302_m1_corrected.fits")
write_stokes_fits(output, corrected_stokes, metadata, calibration=calibration)

# Read back
imported = load_fits_measurement(output)
print("Re-loaded Stokes I shape:", imported.stokes.i.shape)
print("Calibration:", imported.calibration)
print("Header keyword DATE-OBS:", imported.header["DATE-OBS"])
```

### Building a flat-field cache and processing a single measurement

```python
from pathlib import Path
from irsol_data_pipeline.pipeline.filesystem import discover_flatfield_files
from irsol_data_pipeline.pipeline.flatfield_cache import build_flatfield_cache
from irsol_data_pipeline.pipeline.measurement_processor import process_single_measurement
from irsol_data_pipeline.core.models import MaxDeltaPolicy
import datetime

reduced_dir = Path("data/2025/20250312/reduced")
processed_dir = Path("data/2025/20250312/processed")

ff_paths = discover_flatfield_files(reduced_dir)
policy   = MaxDeltaPolicy(default_max_delta=datetime.timedelta(hours=2))
ff_cache = build_flatfield_cache(flatfield_paths=ff_paths, max_delta=policy.default_max_delta)

process_single_measurement(
    measurement_path = reduced_dir / "6302_m1.dat",
    processed_dir    = processed_dir,
    ff_cache         = ff_cache,
    max_delta_policy = policy,
)
```

### Generating a Stokes profile plot

```python
from irsol_data_pipeline.plotting import plot_profile

plot_profile(
    corrected_stokes,
    title="6302 Å | 2025-03-12",
    filename_save="profile.png",
    a0=calibration.wavelength_offset,
    a1=calibration.pixel_scale,
)
```

### Computing slit geometry

```python
from pathlib import Path
from irsol_data_pipeline.io import dat as dat_io
from irsol_data_pipeline.core.models import MeasurementMetadata
from irsol_data_pipeline.core.slit_images.coordinates import compute_slit_geometry

stokes, info = dat_io.read(Path("6302_m1.dat"))
metadata = MeasurementMetadata.from_info_array(info)

slit = compute_slit_geometry(metadata)
print(f"Slit center (solar frame): ({slit.center_solar_x:.1f}, {slit.center_solar_y:.1f}) arcsec")
print(f"μ = {slit.mu:.3f}")
print(f"Slit angle (solar frame): {slit.angle_solar:.3f} rad")
```

### Generating a slit preview image programmatically

```python
from pathlib import Path
from irsol_data_pipeline.pipeline.slit_images_processor import generate_slit_image

generate_slit_image(
    measurement_path=Path("data/2025/20250312/reduced/6302_m1.dat"),
    processed_dir=Path("data/2025/20250312/processed"),
    jsoc_email="your.email@example.com",
    use_limbguider=False,
)
# Writes 6302_m1_slit_preview.png (or 6302_m1_slit_preview_error.json on failure)
```


## 9. Managing Prefect Deployments in Production

This section covers what you need to do when the system runs on a server rather than a development laptop.

### Architecture in production

In production, four long-running processes must be kept alive simultaneously:

```mermaid
graph LR
    subgraph server["Server"]
        PF["Prefect Server
		(make prefect/dashboard)
		Port 4200"]
        WK1["Flat-Field Worker
		(make prefect/serve-flat-field-correction-pipeline)"]
        WK2["Slit Image Worker
		(make prefect/serve-slit-image-pipeline)"]
        WK3["Maintenance Worker
		(make prefect/serve-maintenance-pipeline)"]
    end

    subgraph clients["Access"]
        UI["Browser
		http://server:4200"]
        API["Python / REST
		Prefect API"]
    end

    PF <--> WK1
    PF <--> WK2
    PF <--> WK3
    UI --> PF
    API --> PF
```

- **Prefect Server**: stores flow run history, schedules, and artefacts in a local SQLite database.
- **Flat-Field Worker**: serves the `run-flat-field-correction-pipeline` and `run-daily-flat-field-correction-pipeline` deployments.
- **Slit Image Worker**: serves the `run-slit-image-pipeline` and `run-daily-slit-image-pipeline` deployments. Requires `JSOC_EMAIL` to be set.
- **Maintenance Worker**: serves the `delete-old-prefect-flow-runs` deployment.

> The workers contact the Prefect server and poll for scheduled or manually triggered runs. If a worker is stopped, its deployments will not execute even if the server is running.

### Keeping workers alive (systemd or screen)

Use a process manager to keep all three processes running across reboots. Example using `screen`:

```bash
# Terminal 1 — Prefect server
screen -S prefect-server
make prefect/dashboard
# Ctrl+A, D  to detach

# Terminal 2 — Flat-field correction worker
screen -S ff-worker
make prefect/serve-flat-field-correction-pipeline
# Ctrl+A, D to detach

# Terminal 3 — Slit image generation worker
screen -S slit-worker
JSOC_EMAIL="your.email@example.com" make prefect/serve-slit-image-pipeline
# Ctrl+A, D to detach

# Terminal 4 — Maintenance worker
screen -S maintenance-worker
make prefect/serve-maintenance-pipeline
# Ctrl+A, D to detach
```

For a production setup, prefer `systemd` unit files or a container orchestrator.

### Triggering a run manually

From the UI:
1. Open `http://<server>:4200`.
2. Go to **Deployments**.
3. Select the desired deployment and click **Quick Run** or **Custom Run**.

From the command line (with the Prefect server running):

```bash
# Trigger the full flat-field correction pipeline
uv run prefect deployment run 'process-unprocessed-measurements/run-flat-field-correction-pipeline'

# Trigger a single-day flat-field run with a specific day path
uv run prefect deployment run \
    'process-unprocessed-daily-measurements/run-daily-flat-field-correction-pipeline' \
    --param day_path=/path/to/data/2025/20250312

# Trigger the full slit image generation pipeline
uv run prefect deployment run 'generate-slit-images/run-slit-image-pipeline'

# Trigger a single-day slit image run
uv run prefect deployment run \
    'generate-daily-slit-images/run-daily-slit-image-pipeline' \
    --param day_path=/path/to/data/2025/20250312
```

### Overriding parameters at runtime

When triggering a run from the UI, you can override any parameter defined in the flow function signature:

| Parameter | Flow | Default | Description |
|---|---|---|---|
| `root` | `process-unprocessed-measurements` | `<repo>/data` | Dataset root path |
| `max_delta_hours` | both flat-field flows | `2.0` | Maximum flat-field time gap in hours |
| `max_concurrent_days_to_process` | `process-unprocessed-measurements` | CPU count − 1 (max 12) | How many days to process in parallel |
| `day_path` | `process-unprocessed-daily-measurements` | *(required)* | Path to a single observation day directory |
| `root` | `generate-slit-images` | `<repo>/data` | Dataset root path |
| `jsoc_email` | both slit image flows | `JSOC_EMAIL` env var | JSOC email for SDO data queries |
| `use_limbguider` | both slit image flows | `false` | Use limbguider coordinates when available |
| `max_concurrent_days` | `generate-slit-images` | CPU count − 1 (max 4) | How many days to process in parallel |
| `day_path` | `generate-daily-slit-images` | *(required)* | Path to a single observation day directory |
| `hours` | `delete-flow-runs-older-than` | `672` | Retention window in hours (default: 4 weeks) |
| `interactive` | `delete-flow-runs-older-than` | `false` | Ask for confirmation before deleting (useful in CLI) |

### Monitoring and logs

Prefect stores all logs, task states, and run metadata in its local database:

- **Flow run list**: `http://<server>:4200/runs`
- **Deployment list**: `http://<server>:4200/deployments`
- **Task runs for a flow**: click any flow run to expand its task tree and logs

Each processing run also publishes Prefect **artefacts**:
- A markdown scan summary (total measurements, pending counts per day).
- Per-measurement metadata JSON reports.
- Per-measurement error JSON reports when processing fails.

### Resetting Prefect state

If the Prefect database becomes corrupted or you want a clean slate:

```bash
# WARNING: this deletes ALL flow run history
make prefect/reset
```

After resetting, restart all four processes. The workers will re-register their deployments automatically on the next start.

### Scheduled cleanup

The maintenance deployment handles database growth automatically. Its default schedule (daily at midnight) deletes all flow runs older than 4 weeks. To change the retention window, edit `entrypoints/serve_prefect_maintenance.py` and update the `hours` parameter default, or override it when triggering a manual run.


## 10. Extending the System

### Adding a custom `MaxDeltaPolicy`

`MaxDeltaPolicy` controls how long a flat-field can be from a measurement to still be considered valid. The default applies the same threshold (2 hours) to every measurement.

You can subclass it to apply different thresholds per wavelength or instrument:

```python
import datetime
from irsol_data_pipeline.core.models import MaxDeltaPolicy

class MyPolicy(MaxDeltaPolicy):
    def get_max_delta(
        self,
        wavelength: int,
        instrument: str = "",
        telescope: str = "",
    ) -> datetime.timedelta:
        # Allow a wider window for 8542 Å measurements
        if wavelength == 8542:
            return datetime.timedelta(hours=6)
        return self.default_max_delta

# Use it like this
from irsol_data_pipeline.pipeline.day_processor import process_observation_day
result = process_observation_day(day, max_delta_policy=MyPolicy())
```

### Adding new reference spectra for wavelength calibration

Wavelength calibration works by cross-correlating the measured spectrum against reference spectra bundled in `src/irsol_data_pipeline/core/calibration/refdata/`.

To support a new wavelength:
1. Create a `.npy` reference spectrum file for the new wavelength range.
2. Drop it into `src/irsol_data_pipeline/core/calibration/refdata/`.
3. The calibration code (`autocalibrate.py`) automatically discovers and tries all files in that directory.

Alternatively, pass a custom `refdata_dir` to `calibrate_measurement`:

```python
from irsol_data_pipeline.core.calibration.autocalibrate import calibrate_measurement
from pathlib import Path

calibration = calibrate_measurement(
    stokes=corrected_stokes,
    refdata_dir=Path("/path/to/my/refdata"),
)
```

### Customising the flat-field analysis configuration

The `spectroflat` library accepts a `Config` object that controls the analysis. The default configuration is generated by `create_config_for_data` in `core/correction/analyzer.py`. To override analysis parameters:

```python
from irsol_data_pipeline.core.correction.analyzer import analyze_flatfield
from spectroflat import Config

# Build your own config
config = Config(...)
config.smile.line_distance = 20

dust_flat, offset_map, desmiled = analyze_flatfield(flat_stokes.i, config=config)
```

### Adding a new output format

Output writing is concentrated in `src/irsol_data_pipeline/io/`. To add a new format (e.g. HDF5):

1. Create a new directory `src/irsol_data_pipeline/io/hdf5/` with an `exporter.py`.
2. Implement a `write(path, stokes, metadata, calibration)` function following the same signature pattern as `io/fits/exporter.py`.
3. Call it from `pipeline/measurement_processor.py` after the existing `write_stokes_fits` call.
4. Add the new suffix constant to `core/config.py` and a new `ProcessedOutputKind` literal in `pipeline/filesystem.py`.

### Adding a new Prefect flow

All Prefect flows live in `src/irsol_data_pipeline/orchestration/flows/`. To add a new one:

1. Create a new file, e.g. `orchestration/flows/my_new_flow.py`.
2. Import and apply the conditional decorators:

```python
from irsol_data_pipeline.orchestration.decorators import flow, task

@flow(flow_run_name="my-new-flow/{param}")
def my_new_flow(param: str) -> None:
    ...
```

3. Create a serving entrypoint in `entrypoints/serve_my_new_flow.py`:

```python
from prefect import serve
from irsol_data_pipeline.orchestration.flows.my_new_flow import my_new_flow

deployment = my_new_flow.to_deployment(
    name="my-new-deployment",
    cron="0 2 * * *",   # daily at 02:00
)
serve(deployment)
```

4. Add a `make` target to `Makefile`:

```makefile
prefect/serve-my-new-flow:
    PREFECT_ENABLED=true uv run entrypoints/serve_my_new_flow.py
```

### Running scientific logic outside of Prefect

All `@task` and `@flow` decorators in this codebase are no-ops unless `PREFECT_ENABLED=true`. This means every function decorated with them is a plain Python function in any other context. You can import and call them freely:

```python
# Works without PREFECT_ENABLED and without a running Prefect server
from irsol_data_pipeline.pipeline.scanner import scan_dataset
from irsol_data_pipeline.pipeline.filesystem import discover_observation_days

days = discover_observation_days(root)          # decorated with @task, but still callable
scan = scan_dataset(root)                       # decorated with @task, but still callable
```


## 11. Configuration Reference

All shared constants are defined in `src/irsol_data_pipeline/core/config.py`:

| Name | Default | Description |
|---|---|---|
| `DEFAULT_MAX_DELTA` | `timedelta(hours=2)` | Default maximum allowed time between measurement and flat-field |
| `RAW_DIRNAME` | `"raw"` | Name of the raw data subdirectory inside an observation day |
| `REDUCED_DIRNAME` | `"reduced"` | Name of the reduced data subdirectory (pipeline input) |
| `PROCESSED_DIRNAME` | `"processed"` | Name of the processed output subdirectory |
| `CACHE_DIRNAME` | `"_cache"` | Name of the flat-field cache subdirectory inside `processed/` |
| `CORRECTED_FITS_SUFFIX` | `"_corrected.fits"` | Suffix for corrected FITS output files |
| `ERROR_JSON_SUFFIX` | `"_error.json"` | Suffix for error JSON files |
| `METADATA_JSON_SUFFIX` | `"_metadata.json"` | Suffix for processing metadata files |
| `FLATFIELD_CORRECTION_DATA_SUFFIX` | `"_flat_field_correction_data.pkl"` | Suffix for serialised correction payloads |
| `PROFILE_CORRECTED_PNG_SUFFIX` | `"_profile_corrected.png"` | Suffix for corrected Stokes profile plots |
| `PROFILE_ORIGINAL_PNG_SUFFIX` | `"_profile_original.png"` | Suffix for original Stokes profile plots |
| `SLIT_PREVIEW_PNG_SUFFIX` | `"_slit_preview.png"` | Suffix for slit preview output images |
| `SLIT_PREVIEW_ERROR_JSON_SUFFIX` | `"_slit_preview_error.json"` | Suffix for slit preview error files |
| `SDO_CACHE_DIRNAME` | `"_sdo_cache"` | Name of the SDO FITS cache subdirectory |
| `JSOC_EMAIL` | `""` (from `JSOC_EMAIL` env var) | Email registered with JSOC for SDO data queries |
| `V_STOKES_CUTOFF` | `0.4` | Threshold for filtering high-polarisation rows in auto-calibration |


## 12. Testing

Run the full test suite with coverage:

```bash
make test
```

This runs `pytest` with coverage reports in HTML (`htmlcov/`) and XML (`coverage.xml`).

To run a single test file:

```bash
uv run pytest tests/unit/test_scanner.py -v
```

To run tests matching a keyword:

```bash
uv run pytest -k "flatfield" -v
```

### Test layout

Tests live in `tests/unit/`.
