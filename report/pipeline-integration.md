# Pipeline Integration Points

[← Back to overview](README.md)

This document describes precisely what each type of data artifact must look like, where it must be placed, and how the existing system consumes it. It is addressed directly to Python pipeline developers.

For a concrete replacement plan of legacy production jobs (`quick-look` and `image-generator`), see [Cron migration to irsol-data-pipeline](cron-migration-irsol-data-pipeline.md).

---

## Overview

The system consumes three types of data products per measurement. Your pipeline may produce any combination of them depending on its scope:

| Artifact | What it is | Must land at | Consumed by |
|---|---|---|---|
| **FITS file** | Multi-extension FITS, Stokes I/Q/U/V | `contrast-main` server, local filesystem | FITS generator, downloads, DOI upload, brightness sync |
| **Quicklook image** | JPG preview of the slit spectrograph data | `db.irsol.ch` web server | contrast-main UI modal, SVO `thumbnail_url` |
| **Context image** | JPG of solar disk with slit position | `db.irsol.ch` web server | contrast-main UI modal |

None of these artifacts is uploaded through any web form. They must be placed on the appropriate servers by your pipeline via filesystem write, SCP, SFTP, or equivalent.

---

## 1. FITS files

### What the system expects

The existing pipeline (`brightness-main/datapipeline/datapipeline.py`) is invoked by the PHP application as a subprocess:

```bash
python3 datapipeline/datapipeline.py {input_path} {output_dir}
```

The PHP caller makes three assumptions about any script at this path:
1. **Last line of stdout is the absolute path to the generated FITS file.** The filename is extracted from this line and saved to the database.
2. **If anything goes wrong, the last line of stdout starts with `Error` (capital E).** This triggers a failure branch in the PHP.
3. **The script is blocking.** PHP waits for it to finish before proceeding.

If you wrap or replace `datapipeline.py`, keep this CLI contract exactly.

### Where FITS files must land

```
DATAPIPELINE_DIR/fits/{observation}/{fits_filename}
```

`DATAPIPELINE_DIR` is defined in `contrast-main/config/constants.php`:
```php
const DATAPIPELINE_DIR = "/var/www/html/datapipeline/";
```

So the full path is:
```
/var/www/html/datapipeline/fits/240317/20240317_101530_n5140m1.fits
                                ──────  ────────────────────────────
                            observation      fits_filename
```

The `fits/{observation}/` subdirectory must exist when the pipeline writes the file. The PHP currently creates it with `mkdir()` before calling the script.

### Observed filename convention

From the existing code and sample data, the filename format is:
```
{YYYYMMDD}_{HHMMSS}_{measurement_name}.fits
```

Example: `20240317_101530_n5140m1.fits`

This is the value stored in `measurement.fits_filename` in the contrast DB and propagated downstream to:
- The brightness-main DB (`measurement.fits_filename` via sync payload)
- Zenodo (file uploaded under this name)
- Bulk ZIP downloads (file added under `{observation}/{fits_filename}`)

### FITS file structure

The existing `datapipeline.py` produces a multi-extension FITS file:

| HDU index | Type | Contents |
|---|---|---|
| 0 | `PrimaryHDU` | Header only (SOLARNET-compliant metadata) |
| 1 | `ImageHDU` | Stokes I (`SI` array) |
| 2 | `ImageHDU` | Stokes Q (`SQ` array) |
| 3 | `ImageHDU` | Stokes U (`SU` array) |
| 4 | `ImageHDU` | Stokes V (`SV` array) |

Array shape: `[n_slit_positions, n_wavelength_pixels]` (2D per Stokes parameter).

### Key FITS header fields

These fields are populated by the existing pipeline and expected by downstream consumers (SVO, IrsolDB, `DATA_MAPPINGS`):

| Keyword | Description | Source |
|---|---|---|
| `DATE-OBS` | Observation start datetime (ISO 8601) | `.dat` info block |
| `DATE-END` | Observation end datetime | `.dat` info block |
| `TELESCOP` | Telescope name (`ZIMPOL`/`GREGOR`) | `.dat` info block |
| `INSTRUME` | Instrument name | `.dat` info block |
| `OBSERVER` | Observer name(s) | `.dat` info block |
| `WAVEUNIT` | Wavelength unit (Ångströms) | Calibration |
| `WAVEMIN` | Minimum wavelength in range | Calibration |
| `WAVEMAX` | Maximum wavelength in range | Calibration |
| `SLIT_WID` | Slit width in arcsec | `.dat` info block → converted |
| `INCL_A1` | Slit inclination angle (degrees) | Gaussian fitting on peaks |
| `NSUMEXP` | Number of summed exposures | `.dat` info block |
| `XPOSURE` | Total exposure time (seconds) | `.dat` info block |
| `SOLAR_P0` | Solar P-angle | sunpy computed |
| `STOKES` | Stokes parameters present (e.g. `"IQUV"`) | Pipeline |
| `M_ID` | Measurement ID | `.dat` info block |
| `M_NAME` | Measurement name | `.dat` info block |
| `IMG_TYPE` | Image type | `.dat` info block |

The complete mapping between FITS keywords and IrsolDB fields is in `contrast-main/config/constants.php` under `DATA_MAPPINGS`.

### Python dependencies

The existing pipeline uses:
```
numpy
scipy     (readsav, curve_fit, correlate)
astropy   (fits, units, time)
sunpy     (coordinates.sun.P, angular_radius)
```

Reference spectra are loaded from `.npy` files that must be present at relative path `datapipeline/ref_data5140_irsol.npy` etc. when the script runs.

---

## 2. Quicklook images

### What they are

Quicklook images are JPG previews displayed in the contrast-main management UI and sent to SVO as `thumbnail_url`. They give the publisher a visual sanity check of the spectral slit data.

### URL pattern the system constructs

```javascript
// contrast-main/metadata.php (JavaScript, client-side)
const url = `https://db.irsol.ch/web-site/assets/img_quicklook/${observation}/${measurement}.jpg`;
```

### URL pattern used in SVO publication

```php
// contrast-main/application/models/svo/SvoClient.php
'thumbnail_url' => "https://db.irsol.ch/web-site/assets/img_quicklook/"
                   . $observationName . "/" . $measurement->getName() . ".jpg"
```

### Naming convention

```
{measurement_name}.jpg
```

Example: `n5140m1.jpg` for observation `240317`, stored as:
```
db.irsol.ch:/web-site/assets/img_quicklook/240317/n5140m1.jpg
```

### Delivery

There is no upload API. Your pipeline must place files on the `db.irsol.ch` server directly (SCP/SFTP/rsync or equivalent). The PHP application will reference the URL without checking for existence.

> Because the SVO payload includes this URL, the image **must be deployed before calling `svo-publisher.php`** — otherwise SVO records will reference a non-existent thumbnail.

---

## 3. Context images

### What they are

Context images show the solar disk with the spectrograph slit position indicated — used as spatial orientation previews in the publisher UI.

### URL pattern the system constructs

```javascript
// contrast-main/metadata.php (JavaScript, client-side)
const url = `https://db.irsol.ch/web-site/assets/img_data/${observation}/${measurement}.jpg`;
```

### Naming convention

```
{measurement_name}.jpg
```

Example: `n5140m1.jpg` for observation `240317`, stored as:
```
db.irsol.ch:/web-site/assets/img_data/240317/n5140m1.jpg
```

### Delivery

Same as quicklook images — direct filesystem deployment to `db.irsol.ch`. Not sent to SVO (quicklook only is used there).

---

## How the contrast DB status is set

When your pipeline produces a FITS file and places it at the expected path, the contrast DB needs to know about it. The current flow via the web UI does this automatically (PHP saves `fits_status` and `fits_filename` after `datapipeline.py` completes).

If your pipeline writes files **directly** (bypassing the HTTP trigger), you need to update the DB yourself. The relevant SQL:

```sql
-- Insert or update FITS status for a measurement
INSERT INTO measurement (observation, measurement, svo, fits_status, fits_filename)
VALUES (?, ?, 0, 'GENERATED', ?)
ON DUPLICATE KEY UPDATE fits_status = 'GENERATED', fits_filename = ?;
```

The `sync-check.php` tool (contrast-main) will also auto-discover FITS files on disk that are not yet registered in the DB and set their status to `GENERATED` — so writing the file to the correct path and then running sync-check is a valid alternative to direct DB writes.

---

## How brightness-main learns about new measurements

After FITS generation and any desired publication steps, contrast-main pushes the catalogue to brightness-main via:

```
POST https://brightness-main/api/data-upload.php
Content-Type: application/json

{
  "observations": [
    {
      "name":  "240317",
      "date":  "2024-03-17",
      "measurements": [
        {
          "name":         "n5140m1",
          "lastSync":     null,
          "doi":          "10.5281/zenodo.1234567",
          "fitsFilename": "20240317_101530_n5140m1.fits"
        }
      ]
    }
  ]
}
```

This endpoint uses mutual TLS — the client certificate must be present at the paths configured in `constants.php` (`CERTIFICATE_PATH`, `KEY_PATH`, `CA_PATH`).

The `REPLACE INTO` behaviour means re-sending the same measurement resets its `fits` status in brightness-main to `REQUESTABLE`. Provide `doi` and `fitsFilename` when available so the FITS download link works immediately.

---

## Summary table

| What | Value / path | Set by |
|---|---|---|
| FITS file path | `/var/www/html/datapipeline/fits/{observation}/{YYYYMMDD}_{HHMMSS}_{measurement}.fits` | `datapipeline.py` stdout, then PHP writes file |
| FITS DB record | `contrast.measurement (fits_status='GENERATED', fits_filename=...)` | PHP after datapipeline.py, or `sync-check.php`, or direct DB write |
| Quicklook image | `db.irsol.ch:/web-site/assets/img_quicklook/{observation}/{measurement}.jpg` | External pipeline deployment |
| Context image | `db.irsol.ch:/web-site/assets/img_data/{observation}/{measurement}.jpg` | External pipeline deployment |
| Brightness-main visibility | `brightness.observation` + `brightness.measurement` tables | `POST /api/data-upload.php` from contrast-main |
