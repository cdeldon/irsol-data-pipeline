# Slit Image Creation

Slit image creation generates six-panel contextual preview images showing the spectrograph slit position overlaid on SDO/AIA and SDO/HMI solar images. These previews help researchers visualize exactly where on the solar disc each measurement was taken.


## Purpose

- Compute the spectrograph slit geometry in the solar reference frame.
- Fetch contemporaneous SDO context images (UV, EUV, continuum, magnetogram).
- Render a publication-quality 6-panel figure showing the slit on each data product.
- Provide the **mu** value (cos θ, limb-darkening parameter) for the observation.

## Processing Flow

```mermaid
flowchart TD
    DAT["Load measurement .dat file"]
    META["Extract Measurement Metadata"]
    VALIDATE["Validate solar coordinates<br/>(solar_x, solar_y)"]
    CENTER["Get slit center<br/>(metadata or limbguider)"]
    GEOM["Compute slit geometry<br/>(Earth → solar frame)"]
    MU["Calculate mu<br/>(limb darkening)"]
    SDO["Fetch 6 SDO maps via DRMS<br/>(AIA 1600, 131, 193, 304,<br/>HMI continuum, magnetogram)"]
    RENDER["Render 6-panel figure<br/>(slit overlay + mu circle)"]
    PNG["Save slit preview PNG"]

    DAT --> META --> VALIDATE --> CENTER --> GEOM
    GEOM --> MU
    GEOM --> RENDER
    SDO --> RENDER
    RENDER --> PNG
```

## Caching

Downloaded SDO FITS files are cached in the `processed/_cache/sdo/` directory per observation day, avoiding redundant downloads across measurements.

## Inputs / Outputs

| | Description | Format |
|---|---|---|
| **Input** | Measurement `.dat` file (for metadata) | ZIMPOL IDL save-file |
| **Input** | JSOC email (for DRMS queries) | String |
| **Output** | Slit preview image | PNG file (`*_slit_preview.png`) |
| **Output** | Error metadata (on failure) | JSON file (`*_slit_preview_error.json`) |

## Related Documentation

- [Pipeline Overview](../pipeline/pipeline_overview.md) — slit image generation in the full pipeline
- [Prefect Integration](../pipeline/prefect_integration.md) — scheduling of slit image flows
- [IO Modules](../io/io_modules.md) — metadata import/export
