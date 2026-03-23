# brightness-main — Deep Dive

[← Back to overview](README.md)

## Purpose

`brightness-main` is the **public-facing portal**. Any registered user (no special role required) can:

- Browse solar observations grouped by year, with filters for wavelength, target, and date range.
- See the FITS availability status for each measurement.
- **Request** a FITS file for any measurement that is not yet on the server.
- **Download** a FITS file directly once it has been generated and placed on the server.

Publishers have no additional capabilities here — brightness-main is a pure *consumer* of data produced by contrast-main.

---

## Technology stack

| Layer | Technology |
|---|---|
| Web server | Apache (Docker), configured in `httpd-conf/localhost.conf` |
| Language | PHP 8.x, no framework — vanilla classes wired manually |
| Database | MySQL / MariaDB |
| Auth tokens | Firebase JWT (`vendor/firebase/php-jwt`) |
| External metadata | REST calls to `db.irsol.ch/api/` (IrsolDB) |

---

## Directory layout

```
brightness-main/
├── config/
│   ├── bootstrap.php       # Wires all services into PHP globals:
│   │                       #   $authenticate, $measurementGateway,
│   │                       #   $requestGateway, $irsolDbClient,
│   │                       #   $userGateway, $dataAssembler
│   ├── constants.php       # All configuration: DB host/name, server URLs,
│   │                       #   IrsolDB API URLs, DATA_FIRST_YEAR (2015),
│   │                       #   PYTHON_PATH, DOI_FILE_BASEURL
│   └── messages.php        # User-facing string constants
│
├── application/
│   ├── domain/
│   │   ├── Observation.php     # Data object: name, date, []Measurement
│   │   └── Measurement.php     # Data object: name, fitsStatus, doi,
│   │                           #   fitsFilename, metadata[]
│   ├── exceptions/             # Typed exceptions for auth flows
│   ├── models/
│   │   ├── MeasurementGateway.php   # Read/write to observation + measurement tables
│   │   ├── RequestGateway.php       # Reads a user's pending FITS requests
│   │   ├── UserGateway.php          # User CRUD + authentication
│   │   └── isol-db/
│   │       ├── IrsolDbClient.php    # HTTP client for db.irsol.ch/api/
│   │       └── IrsolDb*.php         # DTOs for IrsolDB responses
│   └── system/
│       ├── Authenticate.php         # JWT session management
│       ├── DataAssembler.php        # Merges local DB + IrsolDB data
│       └── TokenManager.php         # JWT encoding/decoding
│
├── api/                     # JSON REST endpoints — called by contrast-main
│   ├── data-upload.php      # POST  → upsert observations/measurements into DB
│   ├── data-request.php     # GET   → return all obs/measurements as JSON
│   ├── data-remove.php      # POST  → delete measurements (and orphaned observations)
│   └── fits-requests.php    # GET   → (broken) return pending FITS requests
│
├── datapipeline/
│   ├── datapipeline.py           # Python: .dat → .fits conversion
│   ├── ref_data5140_irsol.npy    # Reference spectrum (IRSOL, 5140 Å)
│   ├── ref_data5160_gregor_4p.npy  # Reference spectrum (GREGOR 5160, 4-point)
│   └── ref_data5160_gregor_5p.npy  # Reference spectrum (GREGOR 5160, 5-point)
│
├── web-site/auth/           # Login, register, forgot-password, reset-password pages
│
├── metadata.php             # Main browsing page (no authentication required)
├── request-fits.php         # POST: request or download a FITS file
├── fits-requests.php        # Page: a user's own pending requests
├── delete-fits.php          # GET: cancel a pending FITS request
└── edit-profile.php         # POST + page: update first/last name and password
```

---

## Database schema

```sql
-- An observation session (one or more measurements on a given date)
CREATE TABLE observation (
  name   VARCHAR(15) NOT NULL,   -- e.g. '240317'  (approx. YYMMDD)
  date   DATE        NOT NULL,   -- e.g. '2024-03-17'
  PRIMARY KEY (name)
);

-- A single instrument run within an observation
CREATE TABLE measurement (
  observation   VARCHAR(15) NOT NULL,   -- FK → observation.name
  name          VARCHAR(15) NOT NULL,   -- e.g. 'n5140m1'
  wavelength    INT         NOT NULL,   -- Ångströms (e.g. 5140); often 0 in practice
  fits          ENUM(
      'REQUESTABLE',    -- file not on server yet; user may request it
      'REQUESTED',      -- user has requested; pipeline should generate
      'GENERATED',      -- file present on server; user may download
      'UNAVAILABLE'     -- generation failed or data not available
  ) NOT NULL DEFAULT 'REQUESTABLE',
  requested_by  VARCHAR(50) DEFAULT NULL,  -- email of the requesting user
  doi           VARCHAR(255) DEFAULT NULL, -- Zenodo DOI, e.g. '10.5281/zenodo.xxx'
  fits_filename VARCHAR(255) DEFAULT NULL, -- filename only, no path
  PRIMARY KEY (observation, name)
);

CREATE TABLE user (
  email           VARCHAR(50) NOT NULL,
  first_name      VARCHAR(50) NOT NULL,
  last_name       VARCHAR(50) NOT NULL,
  password        VARCHAR(60) NOT NULL,   -- bcrypt hash
  email_verified  TINYINT(1)  NOT NULL DEFAULT 0,
  publisher       TINYINT(1)  NOT NULL DEFAULT 0,
  PRIMARY KEY (email)
);
```

> **Note on `wavelength`:** The column exists in the schema and is declared in some code paths, but all sample data shows `0`. The wavelength displayed to users is fetched at runtime from IrsolDB, not from this column.

---

## FITS status lifecycle (brightness side)

```
REQUESTABLE ──(user clicks "Request FITS")──────────► REQUESTED
                                                           │
             ◄─(user cancels via delete-fits.php)─────────┘

REQUESTED   ──(contrast generates file + notifies)──► GENERATED
                                                           │
                                                    user can download

[admin]     ──(manual DB update)──────────────────► UNAVAILABLE
```

When a user clicks "Request FITS," `request-fits.php` first checks whether the file already exists in `fits/{observation}/{measurement}.fits` on disk. If it does, the file is streamed immediately; no DB status change. If it does not, the DB record is updated to `REQUESTED`.

> ⚠️ The method that actually saves a FITS request to the DB (`saveFitsRequest`) is currently commented out — see [known-issues.md](known-issues.md).

---

## API endpoints consumed by contrast-main

These endpoints have no user-facing role; they are called machine-to-machine over HTTPS with mutual TLS.

### `POST /api/data-upload.php`

Receives a JSON body describing one year's worth of observations and upserts them into the brightness DB. Existing records are replaced (`REPLACE INTO`), which resets FITS status to `REQUESTABLE`.

**Request body (Content-Type: application/json):**
```json
{
  "observations": [
    {
      "name":  "240317",
      "date":  "2024-03-17",
      "measurements": [
        {
          "name":         "n5140m1",
          "lastSync":     "2024-03-17 10:00:00",
          "doi":          "10.5281/zenodo.1234567",
          "fitsFilename": "20240317_101500_n5140m1.fits"
        }
      ]
    }
  ]
}
```

**Response:** `{"status": "success"}` or `{"error": "..."}`.

### `GET /api/data-request.php`

Returns all observations and measurements currently known to brightness-main, as a nested map. Used by contrast-main's `sync-check.php` to compare catalogues.

**Response:**
```json
{
  "240317": ["n5140m1", "4607_m1"],
  "240510": ["5886_m2", "5886_m14"]
}
```

### `POST /api/data-remove.php`

Same body structure as `data-upload.php`. Deletes the listed measurements, and orphaned observations (with no remaining measurements) are also deleted.

### `GET /api/fits-requests.php`

**Currently broken** — see [known-issues.md](known-issues.md#1-brightness-mainapifits-requestsphp--fetchfitsrequests-missing). Intended to return pending FITS requests so contrast-main can generate and deliver them.

---

## Metadata enrichment (DataAssembler)

The `DataAssembler` class merges two data sources before any page is rendered:

| Source | What it provides |
|---|---|
| Local DB (`MeasurementGateway`) | FITS status, DOI, fits filename, requested_by |
| IrsolDB API (`IrsolDbClient`) | Wavelength (`wlength`), solar target (`target`) |

Configured metadata attributes (in `config/constants.php`):
```php
const METADATA_ATTRIBUTES = [
    "Wavelength" => "wlength",
    "Target"     => "target",
];
```

IrsolDB is queried per observation name using:
- `GET https://db.irsol.ch/api/Observation.php?find&...`
- `GET https://db.irsol.ch/api/Measurement.php?find&...`

---

## Image references (brightness-main)

The public `metadata.php` page does **not** display image previews — those are only shown in contrast-main. The FITS download link in brightness-main points to Zenodo directly when a DOI and filename are present:

```
https://sandbox.zenodo.org/records/{zenodo_id}/files/{fits_filename}
```

(The `sandbox.zenodo.org` URL is a development placeholder — see [known-issues.md](known-issues.md).)
