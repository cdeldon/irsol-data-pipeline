# Installation

This guide covers installing the IRSOL Data Pipeline for both development and production use.

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | ≥ 3.10 | Required runtime |
| **[uv](https://docs.astral.sh/uv/getting-started/installation/)** | Latest | Package manager (recommended) |

## Development Installation

Clone the repository and install in editable mode:

```bash
git clone https://github.com/irsol-locarno/irsol-data-pipeline.git
cd irsol-data-pipeline
# With uv (reccommended)
uv sync
# With pip
pip install -e .
```

This installs the package with all dependencies in a virtual environment. The `idp` CLI command becomes available:

```bash
idp --version
idp info
```

### Make Targets

The project includes a `Makefile` for common development tasks:

| Target | Description |
|--------|-------------|
| `make lint` | Run pre-commit checks (formatting, linting) |
| `make test` | Run pytest with coverage reports |
| `make clean` | Remove cache files, logs, and coverage artifacts |

## Production Installation
[Install](https://docs.astral.sh/uv/getting-started/installation/) `uv` globally and use it to install the pipeline as a standalone tool:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install the package as a standalone tool using `uv` (note: irsol-data-pipeline has been tested on python3.10, and has shown to have problems on higher version of python due to `SpectroFlat` dependency):

```bash
uv tool install irsol-data-pipeline --no-cache-dir --python 3.10
```

Upgrade to the latest version:

```bash
uv tool upgrade irsol-data-pipeline --no-cache-dir --python 3.10
```

After installation, the `idp` command is available globally:

```bash
idp --version
idp info
```

Optionally, install auto-completion of CLI:
```bash
idp --install-completion
source ~/.bashrc
```

> Note: `uv tool install <package>` installs Python CLI tools into isolated, managed environments, adding their executables to your `PATH` for global access. It ensures tools have dedicated environments to prevent dependency conflicts, acting as a faster alternative to `pipx`

## Dependencies

The pipeline relies on the following key dependencies:

### Scientific Computing

| Package | Purpose |
|---------|---------|
| `numpy` (< 2) | Array operations — pinned below 2 because `spectroflat` does not declare a numpy upper bound but its internals are incompatible with numpy 2.x |
| `scipy` (≥ 1.10) | Curve fitting, IDL file reading |
| `astropy` (≥ 5.0) | FITS I/O, coordinates, units |
| `sunpy` (≥ 5.0) | Solar coordinate transforms, Map objects |
| `matplotlib` (≥ 3.7) | Plotting and visualization |

### Domain-Specific

| Package | Purpose |
|---------|---------|
| `spectroflat` (≥ 2.1) | Flat-field and smile correction engine |
| `drms` (≥ 0.7) | JSOC Data Record Management System client |

### Infrastructure

| Package | Purpose |
|---------|---------|
| `prefect` (≥ 3.0) | Workflow orchestration (optional at runtime) |
| `pydantic` (≥ 2.0) | Data validation and domain models |
| `cyclopts` (≥ 4.8) | CLI framework |
| `loguru` (≥ 0.7) | Structured logging |

### JSOC Registration

To generate slit images, register an email with the [JSOC](http://jsoc.stanford.edu/) service for DRMS data queries. Then configure it as a Prefect variable or pass it via CLI arguments.

## Related Documentation

- [Quick Start](quickstart.md) — first steps with the pipeline
- [CLI Usage](../cli/cli_usage.md) — full command reference
- [Prefect Operations](../maintainer/prefect_operations.md) — production deployment guide
