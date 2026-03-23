# Replacing `quick-look` and `image-generator` with `irsol-data-pipeline`

[← Back to overview](README.md)

This document defines a detailed migration plan that assumes `irsol-data-pipeline` is already running on Sirius and scheduled to process all measurements.

Scope of this plan:
1. Resolve compatibility contracts first (names, paths, overwrite behavior, quality).
2. Integrate a compatibility layer into `irsol-data-pipeline` core.
3. Deploy it using Prefect flows and deployments.

Out of scope:
1. Running legacy and new pipelines in parallel during a long transition.

---

## 1. Confirmed migration decisions

These choices are fixed and used throughout this plan.

| Decision | Final value |
|---|---|
| Quicklook profile variant | Use only `*_profile_corrected.*` |
| Original profile handling | Keep `*_profile_original.*` only for debugging on Sirius, do not deploy publicly |
| JPG compression target | JPEG quality `50` |
| Topology | Single-root execution per run, with two concurrent runs (one root for `irsol`, one root for `gregor`) |
| Scheduling | Full Prefect scheduling for generation and deployment |
| Overwrite behavior | Overwrite only with `--force-overwrite`; otherwise skip existing JPG |

---

## 2. Target compatibility contract (must match existing PHP apps)

All generated/deployed outputs must satisfy this contract.

### 2.1 Quicklook output contract

1. Source artifact from `irsol-data-pipeline`: `*_profile_corrected.png`.
2. Deployed artifact: `{measurement}.jpg`.
3. Destination directory:
   `/irsol_db/docs/web-site/assets/img_quicklook/{observation}/`.
4. Public URL expected by apps:
   `https://db.irsol.ch/web-site/assets/img_quicklook/{observation}/{measurement}.jpg`.

### 2.2 Context image output contract

1. Source artifact from `irsol-data-pipeline`: `*_slit_preview.png`.
2. Deployed artifact: `{measurement}.jpg`.
3. Destination directory:
   `/irsol_db/docs/web-site/assets/img_data/{observation}/`.
4. Public URL expected by apps:
   `https://db.irsol.ch/web-site/assets/img_data/{observation}/{measurement}.jpg`.

### 2.3 Non-negotiable naming/parsing rules

1. Observation directory name is unchanged (example: `240317`).
2. Measurement base name is unchanged (example: `n5140m1`, `nw5140m1`, `5886_m14`).
3. Suffix stripping rules:
   - `*_profile_corrected.png` -> measurement base name
   - `*_slit_preview.png` -> measurement base name
4. Ignore `*_profile_original.png` for public deployment.

---

## 3. Compatibility-first work plan

Do these tasks in order before integration into operational flows.

### Stage A - Discovery and naming compatibility

Goal: ensure all production measurement names are discoverable and convertible.

1. Extend measurement filename recognition to include legacy families:
   - `n5140m1.dat`
   - `nw5140m1.dat`
   - `5886_m14.dat`
   - plus currently supported numeric forms.
2. Ensure extraction of canonical `measurement_name` works identically for profile and slit-preview outputs.
3. Add unit tests covering accepted and rejected patterns.

Acceptance criteria:
1. 100% of sampled real `.dat` names parse into expected `measurement_name`.
2. No calibration files (`ff*`, `cal*`) are treated as measurements.

### Stage B - File transformation compatibility

Goal: produce exact JPG artifacts required by `contrast-main` and SVO URLs.

1. Add image conversion routine: PNG -> JPEG with quality `50`.
2. Use `optimize=True` and non-progressive encoding by default for stable output size and compatibility.
3. Convert image mode to RGB before encoding.
4. Preserve deterministic target paths.

Acceptance criteria:
1. All generated JPGs open in browser and have `.jpg` extension.
2. Visual quality is comparable to current legacy output.

### Stage C - Deployment semantics compatibility

Goal: match existing overwrite behavior and idempotency requirements.

1. Default mode: if remote `{measurement}.jpg` exists, skip upload.
2. `--force-overwrite`: always upload and replace.
3. Emit decision logs for each asset: `uploaded`, `skipped_existing`, `failed`.
4. Return non-zero exit code if any upload fails.

Acceptance criteria:
1. Re-running without `--force-overwrite` is a no-op for already deployed assets.
2. Re-running with `--force-overwrite` replaces all targeted assets.

---

## 4. Core integration design inside `irsol-data-pipeline`

Implement compatibility as first-class code in the pipeline package, not a standalone ad hoc script.

### 4.1 Proposed module layout

Suggested additions:

1. `src/irsol_data_pipeline/compat/web_assets/models.py`
2. `src/irsol_data_pipeline/compat/web_assets/discovery.py`
3. `src/irsol_data_pipeline/compat/web_assets/transform.py`
4. `src/irsol_data_pipeline/compat/web_assets/deploy.py`
5. `src/irsol_data_pipeline/compat/web_assets/service.py`
6. `src/irsol_data_pipeline/cli/export_web_assets.py`

Responsibility split:

1. `models.py`: typed models for assets and deployment config.
2. `discovery.py`: find generated PNG artifacts and map to observation/measurement.
3. `transform.py`: PNG to JPEG conversion (quality 50).
4. `deploy.py`: transport abstraction (SFTP/local copy) and overwrite logic.
5. `service.py`: orchestration and reporting.
6. `cli/export_web_assets.py`: command entrypoint.

### 4.2 Proposed CLI surface

Use one command with explicit modes:

```bash
idp export web-assets \
  --root-dir /dati/mdata/pdata/irsol/zimpol \
  --processed-dir /path/to/processed \
  --deploy-quicklook \
  --deploy-context \
  --jpeg-quality 50 \
  --remote-host piombo7.usi.ch \
  --remote-base /irsol_db/docs/web-site/assets \
  [--force-overwrite] \
  [--since 2026-01-01]
```

Rules:
1. `--jpeg-quality` default is `50`.
2. `--deploy-quicklook` deploys corrected profiles only.
3. `--deploy-context` deploys slit previews.
4. `--force-overwrite` controls replacement policy.

### 4.3 Internal processing pipeline

For each discovered artifact:

1. Parse artifact type (`profile_corrected` or `slit_preview`).
2. Extract `observation` and `measurement`.
3. Build target:
   - quicklook -> `img_quicklook/{observation}/{measurement}.jpg`
   - context -> `img_data/{observation}/{measurement}.jpg`
4. Convert PNG to JPEG quality 50.
5. Upload with overwrite policy.
6. Emit structured log event.

### 4.4 Logging and report contract

Emit machine-readable summary at end of run:

```json
{
  "root": "irsol",
  "total": 1200,
  "uploaded": 1130,
  "skipped_existing": 68,
  "failed": 2,
  "duration_seconds": 412.5
}
```

This summary should be available both in logs and as a return object for Prefect tasks.

---

## 5. Prefect integration design

The deployment layer should run as part of first-class Prefect flows, fully scheduled.

### 5.1 Flow model

Define one top-level flow per root directory execution.

Flow: `publish_web_assets_for_root`

Inputs:
1. `root_name` (`irsol` or `gregor`)
2. `root_dir`
3. `processed_dir`
4. `force_overwrite` (default `false`)
5. `jpeg_quality` (default `50`)

Subtasks:
1. `run_generation_for_root` (existing processing flow invocation).
2. `discover_compatible_assets`.
3. `convert_assets_to_jpeg`.
4. `deploy_assets`.
5. `publish_summary`.

### 5.2 Concurrency model for the two roots

Keep each run single-rooted, but schedule two deployments concurrently:
1. Deployment A: root `irsol`
2. Deployment B: root `gregor`

Both deployments execute the same flow with different parameters and independent work pools.

### 5.3 Suggested deployment names

1. `idp-generate-and-publish-irsol`
2. `idp-generate-and-publish-gregor`

### 5.4 Scheduling policy

Use full Prefect scheduling (no cron wrappers).

Example policy:
1. Nightly full generation + publish for each root.
2. Optional daytime incremental publish-only runs.

### 5.5 Retry and failure policy

1. Retry upload task on network failures (`retries=3`, exponential backoff).
2. Fail flow if any artifact deployment fails after retries.
3. Keep generation and deployment task logs separately for diagnostics.

---

## 6. Prefect deployment blueprint

The exact commands may vary by your `idp` CLI, but deployment should follow this shape.

### 6.1 Build and register deployments

1. Build one deployment per root with root-specific parameters.
2. Attach both to the same Prefect work pool/worker class used on Sirius.
3. Set schedules in Prefect, not in system cron.

### 6.2 Required variables / blocks

1. Remote host and auth settings for deployment transport.
2. Remote base path: `/irsol_db/docs/web-site/assets`.
3. JPEG quality: `50`.
4. Force overwrite toggle default: `false`.
5. Optional `since` window for incremental runs.

### 6.3 Operational commands (conceptual)

```bash
# Start Prefect services/worker on Sirius
idp prefect start

# Serve/build generation + publish flows
idp prefect flows serve generate-and-publish-web-assets

# Deploy root-specific schedules
idp prefect deployments apply idp-generate-and-publish-irsol
idp prefect deployments apply idp-generate-and-publish-gregor
```

---

## 7. Testing and validation matrix

### 7.1 Unit tests (core compatibility layer)

1. Filename parsing for all accepted patterns.
2. Suffix mapping to quicklook/context destination.
3. Skip `profile_original` deployment.
4. Overwrite behavior with and without `--force-overwrite`.
5. JPEG conversion enforces quality=50 and RGB mode.

### 7.2 Integration tests (staging endpoint)

1. End-to-end run on one day for each root.
2. Verify remote files exist at both paths:
   - `img_quicklook/{obs}/{measurement}.jpg`
   - `img_data/{obs}/{measurement}.jpg`
3. Verify URLs resolve using HTTP 200.

### 7.3 Product-level checks

1. `contrast-main/metadata.php` quicklook and context modals load.
2. SVO publish succeeds with `thumbnail_url` from quicklook path.
3. No generated quicklook uses `profile_original`.

---

## 8. Implementation backlog (ordered)

1. Extend measurement discovery patterns in core filesystem scanning.
2. Implement `compat/web_assets` module set.
3. Implement `idp export web-assets` CLI.
4. Add full unit test coverage for naming/conversion/overwrite logic.
5. Add Prefect flow `publish_web_assets_for_root`.
6. Add two Prefect deployments (`irsol`, `gregor`) with schedules.
7. Run staging validation matrix and fix any naming/path regressions.
8. Promote to production schedule and monitor summary metrics.

---

## 9. Final cutover definition

Cutover is complete when all conditions are true:

1. Legacy cron jobs for `quick-look` and `image-generator` are disabled.
2. Both Prefect deployments (`irsol`, `gregor`) are enabled and scheduled.
3. Public assets are continuously updated at legacy-compatible URLs.
4. `contrast-main` UI and SVO publication work without code changes in PHP.
