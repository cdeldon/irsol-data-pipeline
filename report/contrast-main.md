# contrast-main — Deep Dive

[← Back to overview](README.md)

## Purpose

`contrast-main` is the **internal publisher portal** used by IRSOL staff. Users with the `PUBLISHER` or `ADMIN` role can:

- Browse all raw observation data available on the Sirius file server.
- Generate FITS files from raw `.dat` data by invoking the Python pipeline.
- Download generated FITS files (single or bulk ZIP).
- Publish observation metadata to IrsolDB via an SSH shell script.
- Create Zenodo DOIs and upload FITS files to Zenodo.
- Publish FITS data and metadata to SVO (Solar Virtual Observatory).
- Push the measurement catalogue to brightness-main, making data visible to end-users.
- Monitor and repair sync state between contrast-main and brightness-main.

Contrast-main is the **only place where data is produced and published**. Brightness-main never writes back to contrast-main.

---

## Technology stack

| Layer | Technology |
|---|---|
| Web server | Apache (Docker) |
| Language | PHP 8.x, no framework |
| Database | MySQL / MariaDB |
| Sirius access | `php-ssh2` extension (SSH + SFTP) |
| Sirius data cache | APCu in-process cache (1-hour TTL) |
| brightness-main API | HTTPS with mutual TLS (client certs in `certificates/`) |
| Zenodo | REST API (`zenodo.org/api`) |
| SVO | SolarNet API (`solarnet.oma.be`) |
| Auth tokens | Firebase JWT |

---

## Directory layout

```
contrast-main/
├── config/
│   ├── bootstrap.php         # Wires all services into PHP globals:
│   │                         #   $authenticate, $measurementGateway,
│   │                         #   $brightnessSyncGateway, $brightnessClient,
│   │                         #   $irsolDbClient, $siriusClient, $svoClient,
│   │                         #   $doiClient, $userGateway, $dataAssembler
│   ├── constants.php         # All config: DB, Sirius paths, Zenodo, SVO, DOI authors,
│   │                         #   mTLS cert paths, DATA_FIRST_YEAR (2021),
│   │                         #   DATAPIPELINE_DIR, METADATA_ATTRIBUTES,
│   │                         #   DATA_MAPPINGS (FITS header → IrsolDB field)
│   └── messages.php
│   # Credentials loaded at runtime (NOT in repo):
│   #   sirius_credentials.php, irsol_db_credentials.php,
│   #   zenodo_access_token.php, svo_api_key.php
│
├── application/
│   ├── domain/
│   │   ├── YearData.php        # Container for one year: []Observation + serialize()
│   │   ├── Observation.php     # name, date, []Measurement, inDb flag + serialize()
│   │   └── Measurement.php     # name, fitsStatus, doi, fitsFilename, metadata[],
│   │                           #   svoUrl, lastSync, path (Sirius path), inDb flag
│   ├── exceptions/
│   ├── models/
│   │   ├── MeasurementGateway.php           # FITS/SVO/DOI status in contrast DB
│   │   ├── BrightnessSyncHistoryGateway.php # Tracks last_sync per measurement
│   │   ├── UserGateway.php
│   │   ├── Role.php                         # ENUM: NONE, PUBLISHER, ADMIN
│   │   ├── brightness/                      # HTTP client + DTOs for brightness-main API
│   │   │   └── BrightnessClient.php
│   │   ├── isol-db/                         # HTTP client for IrsolDB API
│   │   ├── sirius/                          # SSH/SFTP client + DTOs
│   │   │   └── SiriusClient.php
│   │   ├── svo/                             # SolarNet SVO publication client
│   │   │   └── SvoClient.php
│   │   └── doi/                             # Zenodo DOI client
│   │       └── DOIClient.php
│   └── system/
│       ├── Authenticate.php
│       ├── DataAssembler.php   # Merges Sirius data + IrsolDB metadata + local DB status
│       └── TokenManager.php
│
├── sirius_extraction/           # Python scripts that run ON the Sirius server via SSH
│   ├── raw_extractor.py         # Scans raw .z3bd headers → returns obs/measurement JSON
│   ├── measurements_extractor.py # Scans reduced .dat files (alternative; not used in
│   │                              # current fetchData() implementation)
│   └── z3readbd.py              # Binary reader for ZIMPOL3 BD format (.z3bd files)
│
├── datapipeline/                # Empty in this snapshot; pipeline scripts live in
│                                # brightness-main/datapipeline/ and are called from here
│
├── metadata.php                 # Main data management page (PUBLISHER role required)
├── fits-generator.php           # POST: copy .dat from Sirius + run Python pipeline
├── fits-download.php            # GET: stream a single FITS file to the browser
├── fits-bulk-download.php       # POST: create a ZIP of multiple FITS files
├── public-data-uploader.php     # POST: push selected measurements to brightness-main
├── public-data-unpublisher.php  # POST: remove measurements from brightness-main
├── public-data-management.php   # Page: year-level sync history + bulk upload (broken)
├── svo-publisher.php            # POST: publish measurements to SVO
├── svo-unpublisher.php          # POST: remove measurements from SVO
├── db-publisher.php             # POST: publish observation to IrsolDB via SSH
├── doi-create.php               # POST: create or update a Zenodo DOI record
├── doi-get.php                  # GET: fetch existing DOI data from Zenodo
├── sync-check.php               # GET: cross-check brightness sync consistency
├── check-status.php             # GET: poll progress of a running background process
├── conflicts.php                # Page: measurements on Sirius but missing from IrsolDB
├── rules.php                    # Page: display DATA_MAPPINGS (FITS header ↔ IrsolDB)
├── management.php               # Page: user account management (ADMIN role required)
└── edit-profile.php             # POST + page: update first/last name and password
```

---

## Database schema

```sql
-- Per-measurement FITS/SVO/DOI/sync status
CREATE TABLE measurement (
  observation   VARCHAR(15)  NOT NULL,
  measurement   VARCHAR(15)  NOT NULL,
  svo           VARCHAR(255) DEFAULT NULL,  -- SVO URL string, or 0/'' when not published
  fits_status   ENUM(
      'NOT_GENERATED',  -- file does not exist yet
      'GENERATED',      -- file exists in DATAPIPELINE_DIR/fits/
      'ERROR_ONCE',     -- pipeline failed once (may retry)
      'ERROR'           -- pipeline failed twice or more
  ) NOT NULL DEFAULT 'NOT_GENERATED',
  last_sync     DATETIME     DEFAULT NULL,  -- last push to brightness-main
  doi           VARCHAR(255) DEFAULT NULL,  -- Zenodo DOI string
  fits_filename VARCHAR(255) DEFAULT NULL,  -- filename only, no path
  PRIMARY KEY (observation, measurement)
);

CREATE TABLE user (
  email           VARCHAR(50) NOT NULL,
  first_name      VARCHAR(50) NOT NULL,
  last_name       VARCHAR(50) NOT NULL,
  password        VARCHAR(60) NOT NULL,  -- bcrypt hash
  email_verified  TINYINT(1)  NOT NULL DEFAULT 0,
  role            ENUM('NONE', 'PUBLISHER', 'ADMIN') NOT NULL DEFAULT 'NONE',
  PRIMARY KEY (email)
);

-- Per-year record of brightness-main sync operations
-- (no primary key — see known-issues.md)
CREATE TABLE brightness_sync (
  year       INT      NOT NULL,
  last_sync  DATETIME NOT NULL
);
```

> ⚠️ The `contrast.sql` dump in the repo uses a `fits` column with a different ENUM; the live application uses `fits_status`. The dump is outdated. See [known-issues.md](known-issues.md).

---

## Raw data source: Sirius

All instrument files live on the Sirius SSH server. `SiriusClient.php` connects with username/password authentication (credentials not in repo).

**Directory structure on Sirius:**
```
/dati/mdata/rdata/{telescope}/zimpol/{year}/{observation}/
    {measurement}/
        {measurement}_mmd.z3bd      ← raw binary header (ZIMPOL3 BD format)

/dati/mdata/pdata/{telescope}/zimpol/{year}/{observation}/reduced/
    {measurement}.dat               ← reduced data (IDL SAVE / scipy.io.readsav format)
```

`{telescope}` is `irsol` or `gregor`.

### How observations are discovered

When `metadata.php?year=YYYY` is requested, the `DataAssembler` queries three sources in parallel:

| Source | Method | Data returned |
|---|---|---|
| Sirius SSH | `raw_extractor.py {year}` | All observations + measurement names + z3bd header fields |
| IrsolDB API | `IrsolDbClient::fetchObservations()` | Wavelength, observer, project, target, start/end datetime |
| Local contrast DB | `MeasurementGateway::fetchDBData()` | FITS status, SVO URL, last_sync, DOI, fits_filename |

The `DataAssembler::fetchData()` method merges these into `YearData → Observation[] → Measurement[]`.

**Sirius data is cached in APCu for 1 hour** to avoid repeated SSH executions.

### Python scripts on Sirius

`raw_extractor.py` is the script currently in use. It is not run locally — it is executed on the Sirius server itself:

```python
# Called by SiriusClient via:
# ssh2_exec($connection, "python3 raw_extractor.py {year}")

# Scans:
#   /dati/mdata/rdata/irsol/zimpol/{year}/{observation}/{measurement}/{measurement}_mmd.z3bd
#   /dati/mdata/rdata/gregor/zimpol/{year}/...

# Output: JSON to stdout
{
  "240317": {
    "date": "2024-03-17T...",
    "measurements": [
      {"name": "n5140m1", "path": "/dati/.../_mmd.z3bd", "info": "..."}
    ]
  }
}
```

`measurements_extractor.py` is an alternative that reads reduced `.dat` files instead of raw `.z3bd` files. It is present but not invoked in the current `SiriusClient.fetchData()`.

---

## FITS generation

This is the central data production step. The complete flow:

```
[Publisher UI: metadata.php]
    │
    │ POST year + {observation: [measurement, ...]}
    ▼
fits-generator.php (PHP)
    │
    ├─ 1. SiriusClient::copyMeasurementFromSirius()
    │      Source:  /dati/mdata/pdata/{telescope}/zimpol/{year}/{obs}/reduced/{mes}.dat
    │      Dest:    DATAPIPELINE_DIR/fits/{observation}/{measurement}.dat
    │      Method:  SFTP stream copy
    │
    ├─ 2. shell_exec("python3 datapipeline/datapipeline.py {input_path} {output_dir}")
    │      input_path = DATAPIPELINE_DIR/fits/{observation}/{measurement}.dat
    │      output_dir = DATAPIPELINE_DIR/fits/{observation}/
    │      → Last line of stdout: full path to generated .fits file
    │      → Any line starting with "Error": treated as failure
    │
    ├─ 3. Parse output filename from last stdout line
    │      → UPDATE contrast DB: fits_status = GENERATED, fits_filename = {filename}
    │
    └─ 4. Delete working .dat file

FITS file lives at:
    /var/www/html/datapipeline/fits/{observation}/{fits_filename}
    (i.e. DATAPIPELINE_DIR/fits/{observation}/{fits_filename})
```

Progress is tracked via PHP session variables and polled by the browser via `check-status.php`.

If a FITS file already exists at the expected path, generation is skipped and the DB status is set to `GENERATED` immediately (idempotent re-run).

**DATAPIPELINE_DIR** is defined in `constants.php`:
```php
const DATAPIPELINE_DIR = "/var/www/html/datapipeline/";
```

---

## Publication flows

### → brightness-main ("Upload to public")

```
public-data-uploader.php
    → BrightnessClient::uploadMeasurements(YearData)
        → POST https://brightness-main/api/data-upload.php
            Body: YearData::serialize() as JSON
    → BrightnessSyncHistoryGateway::saveSync(YearData)
        → UPDATE contrast DB: last_sync = NOW() for each measurement
```

Only measurements that match the user's checkbox selection are included (via `DataAssembler::fetchData($year, $filter)`).

### → brightness-main unpublish

```
public-data-unpublisher.php
    → BrightnessClient::removeMeasurements(YearData)
        → POST https://brightness-main/api/data-remove.php
    → BrightnessSyncHistoryGateway::removeSync(YearData)
        → UPDATE contrast DB: last_sync = NULL
```

### → IrsolDB ("Publish to IrsolDB")

```
db-publisher.php
    → SiriusClient::publishObservation(year, observationName)
        → ssh2_exec: "sh z3addobservation_to_database.sh
                       /data/mdata/rdata/zimpol/{year}/{observation}"
          (script runs on the Sirius server itself)
```

stderr output from the script is treated as an error and stored in the PHP session.

### → Zenodo DOI ("Publish DOI")

```
doi-create.php  (receives grouped measurement lists + title/authors/description)
    │
    ├─ New DOI:
    │    → DOIClient::upload(data)
    │        → POST https://zenodo.org/api/deposit/depositions
    │        → Upload FITS files from DATAPIPELINE_DIR/fits/{obs}/{fits_filename}
    │        → Publish deposition
    │        → UPDATE contrast DB: doi + fits_filename per measurement
    │
    └─ Update existing DOI:
         → DOIClient::update(data, deposition_id)
             → Adds new file versions to existing Zenodo record
```

The publisher groups measurements, sets a title, picks authors from the pre-configured `DOI_AUTHORS` list (in `constants.php`), and writes a description. Multiple measurements can share one DOI record.

### → SVO

```
svo-publisher.php
    → SvoClient::publishMeasurements(YearData)
        → POST https://solarnet.oma.be (SolarNet API)
        → Payload includes:
            thumbnail_url: "https://db.irsol.ch/web-site/assets/img_quicklook/
                             {observation}/{measurement}.jpg"
        → UPDATE contrast DB: svo = returned SVO URL
```

> ⚠️ The `thumbnail_url` references images on `db.irsol.ch`. These images must exist **before** SVO publication — see [pipeline-integration.md](pipeline-integration.md).

---

## Image references (contrast-main)

Two image previews are shown per measurement in the `metadata.php` UI. Both are loaded **client-side via JavaScript** by constructing the URL from the observation and measurement names. The PHP server is not involved in fetching or caching them.

| Button label | URL pattern | Notes |
|---|---|---|
| Context Image | `https://db.irsol.ch/web-site/assets/img_data/{observation}/{measurement}.jpg` | Shows solar disk with slit position |
| Quicklook Image | `https://db.irsol.ch/web-site/assets/img_quicklook/{observation}/{measurement}.jpg` | Slit spectrograph preview |

The application **does not check whether these images exist** before showing the button — a 404 from `db.irsol.ch` means a broken image in the modal.

Neither contrast-main nor brightness-main has any mechanism for uploading these images. They must be placed on `db.irsol.ch` by an external process.

---

## Metadata attribute mapping (`DATA_MAPPINGS`)

`constants.php` defines a large `DATA_MAPPINGS` table that maps FITS header keywords to IrsolDB field names. This is what controls what metadata is synced between FITS headers and the IrsolDB. Python pipelines should use this as the authoritative list of which FITS header fields matter to the system:

```php
const DATA_MAPPINGS = [
    'DATE'      => 'start_datetime',
    'DATE_END'  => 'end_datetime',
    'TELESCOP'  => 'fk_telescope-name',
    'WLENGTH'   => 'wlength',
    'OBSERVER'  => 'observer',
    'MPROJECT'  => 'mproject',
    'STOKES'    => 'stokes',
    'SLIT_WID'  => ... (mapped to spectrograph params),
    ... (40+ fields total)
];
```

The full list is visible in [contrast-main/config/constants.php](../contrast-main/config/constants.php).

---

## How `sync-check.php` works

This is a consistency/diagnostic tool. When called:

1. Reads `measurement.fits_status = 'GENERATED'` from contrast DB.
2. Verifies each FITS file actually exists at its expected path on disk.
3. Scans `datapipeline/fits/` on disk and finds files not registered in the DB.
4. Calls `BrightnessClient::getRemoteData()` (brightness `data-request.php` API).
5. Cross-checks which measurements are tracked in brightness but not in contrast's `last_sync` records, and vice versa.

Returns a JSON summary of inconsistencies. Does not auto-repair.
