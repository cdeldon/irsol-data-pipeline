# End-to-End Data Flow

[← Back to overview](README.md)

This document walks through the complete lifecycle of a solar observation — from the moment the telescope finishes recording to the point where a scientist downloads a FITS file.

---

## Complete lifecycle at a glance

```
[Telescope / Instrument]
         │
         │  (automatic, no operator action)
         ▼
[Sirius file server]
  raw:      /dati/mdata/rdata/{telescope}/zimpol/{year}/{obs}/{mes}/{mes}_mmd.z3bd
  reduced:  /dati/mdata/pdata/{telescope}/zimpol/{year}/{obs}/reduced/{mes}.dat
         │
         │  SSH — raw_extractor.py {year}
         ▼
[contrast-main discovers new data]
  DataAssembler merges:
    • Sirius observation list  (SSH Python script)
    • IrsolDB metadata         (HTTP REST)
    • Local contrast DB status (MySQL)
         │
         │  Publisher selects measurements in the UI
         ▼
[FITS generation]
  1. SFTP: Sirius .dat → contrast server (working copy)
  2. shell_exec: datapipeline.py .dat → .fits
  3. Delete .dat; save fits_filename + GENERATED status to DB
         │
         ├──────────────────────────────────────────────────────────────┐
         │                                                              │
         ▼ (IrsolDB publication)              ▼ (DOI + SVO)            │
[db-publisher.php]                    [doi-create.php]                 │
SSH: z3addobservation_to_database.sh  Zenodo REST API                  │
on Sirius server                      → DOI + fits uploaded            │
                                      → DOI saved to contrast DB       │
                                                                        │
                                      [svo-publisher.php]              │
                                      SolarNet API                     │
                                      → needs quicklook image at       │
                                        db.irsol.ch/img_quicklook/     │
                                        (placed by pipeline)           │
                                                                        │
         ◄──────────────────────────────────────────────────────────────┘
         │
         │  Publisher clicks "Upload to public"
         ▼
[public-data-uploader.php]
  POST /api/data-upload.php  →  [brightness-main]
  Payload: YearData::serialize() as JSON
  brightness DB: REPLACE INTO observation + measurement (status = REQUESTABLE)
         │
         ▼
[brightness-main: data visible to end-users]
  metadata.php shows observations/measurements with FITS badges
         │
         │  End-user clicks "Request FITS"
         ▼
[request-fits.php]
  IF file already on disk → stream FITS directly (no DB change)
  IF file not on disk     → set DB status = REQUESTED
                            (intended: contrast picks up and delivers)
                            ⚠️  cross-system delivery flow is BROKEN
                            see known-issues.md
         │
         │  (file already on disk path, or delivered by publisher)
         ▼
[User downloads .fits file]
  Streamed from brightness-main server
  OR linked directly to Zenodo record (DOI_FILE_BASEURL/{zenodo_id}/files/{filename})
```

---

## Step-by-step walkthrough

### Step 1 — Data arrives on Sirius

Telescope control software writes raw and reduced instrument files to Sirius automatically after each observation session. There is no action needed from application operators.

File naming conventions:
- Observation name: approx. `YYMMDD` or `YYYYMMDD` (e.g. `240317` = 2024-03-17).
- Measurement name: encodes wavelength line and sequence (e.g. `n5140m1` = narrow slit, 5140 Å, measurement 1).

---

### Step 2 — contrast-main discovers new data

Visiting `metadata.php?year=YYYY` in contrast-main triggers the full three-way data merge:

**2a. Sirius inventory via SSH:**

`SiriusClient::fetchData(year)` opens an SSH connection and runs:
```
python3 raw_extractor.py {year}
```
on the Sirius server itself. The script scans both the IRSOL and GREGOR subdirectories under `/dati/mdata/rdata/.../zimpol/{year}/`, reads the `.z3bd` binary header of each measurement, and returns a JSON document:
```json
{
  "240317": {
    "date": "2024-03-17T...",
    "measurements": [
      {"name": "n5140m1", "path": "/dati/.../n5140m1_mmd.z3bd", "info": "..."}
    ]
  }
}
```
This result is cached in APCu for 1 hour to avoid repeated SSH round-trips.

**2b. IrsolDB metadata:**

`IrsolDbClient::fetchObservations()` queries `db.irsol.ch/api/` for the following attributes per measurement:
- `wlength` (wavelength)
- `observer`
- `mproject` (project)
- `target`
- `start_datetime`, `end_datetime`

**2c. Local contrast DB status:**

`MeasurementGateway::fetchDBData()` returns: `fits_status`, `svo`, `last_sync`, `doi`, `fits_filename` for every observation passed in.

**What gets shown:** The merged view tells the publisher which measurements exist on Sirius, whether they are in IrsolDB, and what their FITS/SVO/DOI status is in the local DB.

---

### Step 3 — FITS generation

The publisher selects one or more measurements and clicks "Generate FITS."

**PHP side (`fits-generator.php`):**
1. Calls `SiriusClient::copyMeasurementFromSirius()`:
   - Source: `/dati/mdata/pdata/{telescope}/zimpol/{year}/{obs}/reduced/{mes}.dat` (on Sirius)
   - Destination: `DATAPIPELINE_DIR/fits/{observation}/{measurement}.dat` (on contrast server, SFTP)
2. Invokes the Python pipeline:
   ```bash
   python3 datapipeline/datapipeline.py \
       datapipeline/fits/{observation}/{measurement}.dat \
       datapipeline/fits/{observation}/
   ```
3. Parses the last line of stdout (the output FITS filepath), extracts the filename.
4. Saves `fits_status = GENERATED` and `fits_filename` to the contrast DB.
5. Deletes the working `.dat` file.

**Python side (`datapipeline.py`):**
- Reads the IDL SAVE format `.dat` file using `scipy.io.readsav`.
- Identifies the correct reference spectrum (auto-selects from 3 reference datasets via cross-correlation).
- Performs wavelength calibration (Gaussian peak fitting → pixel-to-wavelength transform).
- Calculates slit inclination correction.
- Reads instrument metadata (slit width, exposure time, image type, etc.) from the `.dat` info block.
- Computes solar geometry parameters (P-angle, angular radius) using `sunpy`.
- Outputs a multi-extension FITS file with SOLARNET-compliant headers.

Output file lands at:
```
DATAPIPELINE_DIR/fits/{observation}/{datetime}_{measurement}.fits
      i.e. /var/www/html/datapipeline/fits/240317/20240317_101530_n5140m1.fits
```

If the output file already exists, generation is skipped (idempotent).

---

### Step 4 — Publication to external registries

These steps are independent of each other and can be done in any order after FITS generation.

#### IrsolDB publication
The publisher clicks "Publish to IrsolDB" for an observation. This triggers:
```
SiriusClient::publishObservation(year, observationName)
    → SSH: sh z3addobservation_to_database.sh
              /data/mdata/rdata/zimpol/{year}/{observation}
```
The shell script runs on the Sirius server and populates the IrsolDB. This is the step that makes the observation appear in IrsolDB metadata queries.

#### Zenodo DOI publication
The publisher groups one or more FITS files, sets title, description, and authors, then triggers `doi-create.php`. The `DOIClient`:
1. Creates a new Zenodo deposition.
2. Uploads each FITS file from `DATAPIPELINE_DIR/fits/{obs}/{fits_filename}`.
3. Sets the configured community (`irsol`), license (`cc-by-sa-4.0`), and attribution text.
4. Publishes the deposition.
5. Saves the resulting DOI and `fitsFilename` back to the contrast DB and (via sync) to brightness-main.

Existing depositions can be updated (new file versions uploaded) via the same `doi-create.php` with an `update` flag.

#### SVO publication
`SvoClient::publishMeasurements()` sends measurement metadata to `solarnet.oma.be`. The payload includes:
```php
'thumbnail_url' => "https://db.irsol.ch/web-site/assets/img_quicklook/{obs}/{mes}.jpg"
```
> This URL **must resolve** before SVO publication. The image must be in place on `db.irsol.ch` first.

---

### Step 5 — Push to brightness-main

The publisher selects measurements and clicks "Upload to public." This:
1. Calls `BrightnessClient::uploadMeasurements(YearData)`, POSTing serialized measurement data to brightness-main's `/api/data-upload.php`.
2. Records `last_sync = NOW()` in the contrast DB for each pushed measurement.

From this moment, the measurements appear in the public `metadata.php` portal with status `REQUESTABLE`.

---

### Step 6 — End-user downloads FITS

The end-user visits `brightness-main/metadata.php?year=YYYY`.

**If the measurement has a DOI:**
A "Download FITS" link points directly to Zenodo:
```
https://zenodo.org/records/{zenodo_id}/files/{fits_filename}
```

**If the measurement has no DOI but a FITS file is on the brightness server:**
The user clicks "Request FITS." PHP checks for `fits/{observation}/{measurement}.fits` on disk; if present, the file is streamed directly.

**If neither is true:**
The user clicks "Request FITS" — the DB is updated to `REQUESTED`. The intended flow is that contrast-main polls brightness API for pending requests and delivers the file — but this is currently broken (see [known-issues.md](known-issues.md)).

---

## What the system does NOT handle

| Concern | Current state |
|---|---|
| Image upload (quicklook, context) | Not handled — images must be deployed to `db.irsol.ch` externally |
| Automatic FITS delivery from contrast → brightness | Partially implemented but broken |
| Automated/scheduled pipeline trigger | No scheduling — all generation is manual, publisher-triggered |
| User registration (self-service) | Exists in brightness-main only; contrast-main uses invite-only flow |
