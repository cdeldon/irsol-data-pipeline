# Known Issues and Inconsistencies

[← Back to overview](README.md)

**Status:** As-is snapshot, March 2026.
**Purpose:** Reference for anyone working around or fixing existing breakage.
**Scope:** These are issues found in the source code without running the system. They do not block pipeline development but explain why certain features behave unexpectedly.

---

## Critical: Broken method calls

These are server-side errors ($PHP Fatal error) that would be raised if the relevant pages or endpoints are triggered.

### 1. `brightness-main/api/fits-requests.php` — `fetchFitsRequests()` missing

**Location:** [brightness-main/api/fits-requests.php](../brightness-main/api/fits-requests.php) line 36
**Calls:** `$measurementGateway->fetchFitsRequests()`
**Problem:** This method is commented out in `MeasurementGateway.php` — only a partial stub remains in the commented block.

**Impact:** The endpoint that contrast-main polls to discover pending FITS requests does not work. The entire cross-system FITS delivery workflow (contrast automatically picking up requests and generating files for brightness users) is non-functional. Currently, FITS files must be placed on the brightness server manually or through an alternative mechanism.

---

### 2. `brightness-main/request-fits.php` — `saveFitsRequest()` missing

**Location:** [brightness-main/request-fits.php](../brightness-main/request-fits.php) line 24
**Calls:** `$measurementGateway->saveFitsRequest($observation, $measurement, $user->getEmail())`
**Problem:** Same cause as above — `saveFitsRequest()` exists only in the commented-out block of `MeasurementGateway.php`.

**Impact:** When a registered user in brightness-main clicks "Request FITS" for a measurement that is not yet on disk, the page throws a fatal error. The request is never saved to the DB.

---

### 3. `brightness-main/application/models/RequestGateway.php` — Wrong `LocalMeasurement` constructor

**Location:** [brightness-main/application/models/RequestGateway.php](../brightness-main/application/models/RequestGateway.php) line 29
**Problem:** Instantiates `LocalMeasurement` with 4 arguments. The actual constructor signature in `LocalMeasurement.php` requires 5.

**Impact:** Fatal error when `RequestGateway::fetchFitsRequests()` is called (the user-facing "FITS requests" page in brightness-main).

---

### 4. `contrast-main/public-data-management.php` — `fetchSyncHistory()` missing

**Location:** [contrast-main/public-data-management.php](../contrast-main/public-data-management.php) line 20
**Calls:** `$brightnessSyncGateway->fetchSyncHistory()`
**Problem:** `BrightnessSyncHistoryGateway` does not implement `fetchSyncHistory()`. The class has `checkIfSynced()`, `saveSyncTime()`, `fetchAllSyncedMeasurements()`, and `saveSync()`, but not `fetchSyncHistory()`.

**Impact:** The `public-data-management.php` page (year-level sync history) crashes on load.

---

### 5. `contrast-main/application/domain/Measurement.php` — `$wavelength` undefined

**Location:** [contrast-main/application/domain/Measurement.php](../contrast-main/application/domain/Measurement.php) `getWavelength()` method
**Problem:** Returns `$this->wavelength`, but the class has no `$wavelength` property declared. The contrast-main `Measurement` domain object does not carry wavelength — it is fetched from IrsolDB at runtime.

**Impact:** PHP notice/warning if `getWavelength()` is ever called. It does not appear to be called in currently visible code paths.

---

## Schema inconsistencies

### 6. `contrast.sql` uses `fits` column; application uses `fits_status`

The SQL dump file (`contrast-main/contrast.sql`) defines the `measurement` table with a column named `fits`:
```sql
`fits` enum('NOT_GENERATED','GENERATED','ERROR_ONCE','ERROR')
```

All PHP gateway code reads and writes `fits_status`. The dump is an outdated snapshot and does not reflect the live DB schema.

**Impact:** Running the dump as-is would create a broken DB. The column must be named `fits_status`.

---

### 7. `brightness.sql` missing columns present in application code

The DB dump (`brightness-main/brightness.sql`) does not include `doi` or `fits_filename` columns in the `measurement` table. However, `MeasurementGateway::saveData()` issues `REPLACE INTO` statements with both columns.

**Impact:** Running the dump and then the application would cause SQL errors on any data-upload call from contrast-main.

---

### 8. `brightness_sync` table has no primary key and has duplicate rows

The `brightness_sync.sql` dump shows:
```sql
CREATE TABLE brightness_sync (
  year      INT      NOT NULL,
  last_sync DATETIME NOT NULL
);
-- followed by 15 rows including several duplicate year values
```

There is no `PRIMARY KEY` or `UNIQUE KEY`. `BrightnessSyncHistoryGateway` only ever INSERTs into this table, never UPDATEs — so sync history accumulates without bound.

**Impact:** The table functions as an append-only log, which is probably intentional for history tracking, but the missing constraint means no deduplication.

---

## Configuration issues

### 9. `brightness-main/constants.php` — Windows Python path

```php
const PYTHON_PATH = 'C:\Users\Leand\anaconda3\Scripts\conda.exe';
```

This is a local Windows development leftover. The production path should be `python3` (or a virtual environment path), as already set in `contrast-main/constants.php`:
```php
const PYTHON_PATH = 'python3';
```

**Impact:** The Python pipeline cannot be invoked from brightness-main on any Linux server until this is corrected.

---

### 10. Credential files are not in the repository

`contrast-main/config/bootstrap.php` requires these files, which must be created on the deployment server:

| File | Contents |
|---|---|
| `sirius_credentials.php` | `SIRIUS_HOST`, `SIRIUS_PORT`, `SIRIUS_USERNAME`, `SIRIUS_PASSWORD` |
| `irsol_db_credentials.php` | IrsolDB API credentials |
| `zenodo_access_token.php` | `ZENODO_ACCESS_TOKEN` |
| `svo_api_key.php` | SVO API key |

`brightness-main/config/bootstrap.php` similarly requires:
- `irsoldb_credentials.php`
- `db_credentials.php` (`DB_USER`, `DB_PASS`)

**Impact:** Application fails to boot on a fresh checkout without these files in place.

---

### 11. DOI URLs point to Zenodo sandbox

```php
const DOI_BASE_ADDRESS = 'https://zenodo.org/api';   // OK
const DOI_RECORDS_URL  = 'https://zenodo.org/records/'; // OK
const DOI_FILE_BASEURL = "https://sandbox.zenodo.org/records/"; // ← sandbox!
```

`DOI_FILE_BASEURL` — used to build the download link in brightness-main `metadata.php` — points to the Zenodo **sandbox** (test environment). Production deployment requires switching this to `https://zenodo.org/records/`.

---

## Python script issues

### 12. `z3readbd.py` — variable name typo in assertion

**Location:** [contrast-main/sirius_extraction/z3readbd.py](../contrast-main/sirius_extraction/z3readbd.py) line 110
**Code:**
```python
assert betx == bETX, 'ETX missing or misplaced; etx=' + str(ord(etx))
#                                                              ^^^
#                                                 should be: betx
```

**Impact:** If the assertion fires (malformed `.z3bd` file), Python raises a `NameError: name 'etx' is not defined` instead of the intended `AssertionError`. Normal file reading is unaffected.

---

### 13. `datapipeline.py` — potentially uninitialized variables

Static analysis identifies these at runtime-path-dependent initializations:

| Variable | Location | Condition |
|---|---|---|
| `coords` | line ~350, `e_to_s()` call | Only assigned inside an `if` block |
| `int_time` | line ~355, `XPOSURE` header | Assigned inside a loop over `.dat` keys |
| `tot_images` | line ~355, `XPOSURE` header | Same loop |

**Impact:** If the input `.dat` file lacks the relevant metadata keys (e.g. `measurement.datetime`, `measurement.images`, `measurement.integration_time`), these variables may be uninitialized when used, causing a `NameError` or `UnboundLocalError`.

---

## Open TODOs in source code

Items marked `//TODO` or similar in the codebase that affect pipeline integration:

| Location | TODO |
|---|---|
| Both `constants.php` | `CONTACT_EMAIL` is an empty string |
| `contrast-main/constants.php` | `BRIGHTNESS_ENABLED = false` — but brightness API is actively used |
| Both `constants.php` | `PREFIX_URL` points to `localhost` — must be updated for deployment |
| `contrast-main/fits-generator.php` | FITS generation is hard-coded to use `irsol/zimpol` source path; GREGOR handling may need review |
| Both README files | "Hide Generate FITS for measurements with wavelength != 5140 (Has to be verified)" |
| `brightness-main/request-fits.php` | Comment: `# TODO use a more robust directory traversal` — current path is manually constructed from user-supplied `$observation` and `$measurement` parameters |
