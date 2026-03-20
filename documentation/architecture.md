# Repository Architecture

## Design Goals

- Keep scientific logic reusable without prefect runtime.
- Isolate I/O formats from science algorithms.
- Keep Prefect concerns inside `prefect/`, with package-installed command implementations in `cli/`.

## High-Level Structure

```mermaid
flowchart TB
    CORE["core
    science + models + slit geometry"]
    IO["io
    format adapters"]
    PIPE["pipeline
    dataset/day/measurement orchestration"]
    ORCH["orchestration
    Prefect flows, variables, logging bridge"]
    CLI["cli
    package-installed command entry points"]
    ENTRY["entrypoints
    thin compatibility wrappers"]

    CORE --> PIPE
    IO --> PIPE
    PIPE --> ORCH
    ORCH --> CLI
    CLI --> ENTRY
```

## Source Tree (Current)

```text
src/irsol_data_pipeline/
├── core/
│   ├── config.py
│   ├── models.py
│   ├── calibration/
│   │   ├── autocalibrate.py
│   │   └── refdata/
│   ├── correction/
│   │   ├── analyzer.py
│   │   └── corrector.py
│   └── slit_images/
│       ├── config.py
│       ├── coordinates.py
│       ├── solar_data.py
│       └── z3readbd.py
├── io/
│   ├── dat/importer.py
│   ├── fits/{importer.py, exporter.py}
│   ├── flatfield/{importer.py, exporter.py}
│   └── processing_metadata/{importer.py, exporter.py}
├── pipeline/
│   ├── filesystem.py
│   ├── scanner.py
│   ├── flatfield_cache.py
│   ├── measurement_processor.py
│   ├── day_processor.py
│   ├── slit_images_processor.py
│   └── cache_cleanup.py
├── prefect/
│   ├── decorators.py
│   ├── patch_logging.py
│   ├── retry.py
│   ├── utils.py
│   ├── variables.py
│   └── flows/
│       ├── flat_field_correction.py
│       ├── slit_image_generation.py
│       ├── tags.py
│       └── maintenance/
│           ├── delete_old_prefect_data.py
│           └── delete_old_cache_files.py
├── cli/
│   ├── app.py
│   ├── common.py
│   ├── flows.py
│   ├── info.py
│   ├── metadata.py
│   └── variables.py
├── plotting/
│   ├── profile.py
│   └── slit.py
├── exceptions.py
├── logging_config.py
└── version.py
```

## Command Layout

- `src/irsol_data_pipeline/cli/` contains the Cyclopts-based unified CLI implementation.
- `app.py` defines the root command and mounts lazy-loaded sub-apps for `flows` and `variables`.
- `flows.py`, `variables.py`, and `info.py` implement operator-facing commands, while `metadata.py` and `common.py` centralize shared registries and helpers.

## Execution Paths

| Path | Trigger | Main modules |
|---|---|---|
| Single measurement | `entrypoints/process_single_measurement.py` | `pipeline/measurement_processor.py`, `core/correction`, `core/calibration`, `io/fits` |
| Flat-field batch | Prefect flow `ff-correction-full` / `ff-correction-daily` | `prefect/flows/flat_field_correction.py`, `pipeline/day_processor.py` |
| Slit preview batch | Prefect flow `slit-images-full` / `slit-images-daily` | `prefect/flows/slit_image_generation.py`, `pipeline/slit_images_processor.py` |
| Maintenance | Prefect flow `maintenance-cleanup` / `maintenance-cache-cleanup` | `prefect/flows/maintenance/*`, `pipeline/cache_cleanup.py` |

## Boundaries

- `core/` has no file-format policy and no scheduling policy.
- `io/` does not perform scientific transformations.
- `pipeline/` contains process logic but no Prefect deployment definitions.
- `prefect/` owns flow wiring and deployment construction.
- `cli/` owns package-installed command implementations for serving, inspection, and Prefect variable bootstrapping.
- `entrypoints/` contains development scripts for local testing and experimentation.

For direct Python usage patterns, see [library-usage.md](library-usage.md).
