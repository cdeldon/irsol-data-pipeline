"""Constants and configuration for slit image generation."""

from __future__ import annotations

import astropy.units as u
from astropy.coordinates import EarthLocation

# IRSOL observatory location (Gregory telescope)
IRSOL_LOCATION = EarthLocation(
    lat=46.176906 * u.deg,
    lon=8.788521 * u.deg,
    height=503.4 * u.m,
)

# Derotator coordinate system mapping:
#   True  → equatorial (needs rotation to solar frame)
#   False → heliographic (already in solar frame)
DEROTATOR_COORDINATE_SYSTEMS: dict[int, bool] = {
    0: True,  # equatorial
    1: False,  # heliographic
}

# Telescope-specific slit dimensions
TELESCOPE_SPECS: dict[str, dict] = {
    "gregor": {
        "slit_radius": 44 / 2,  # arcsec (half-length)
        "slit_width_fn": lambda _: 0.25,  # constant slit width at GREGOR
    },
    "irsol": {
        "slit_radius": 140 * 1.3 / 2,  # arcsec
        "slit_width_fn": lambda x: x * 7.9,
    },
    "gregory irsol": {
        "slit_radius": 140 * 1.3 / 2,  # arcsec
        "slit_width_fn": lambda x: x * 7.9,
    },
}

DEFAULT_TELESCOPE_SPEC = TELESCOPE_SPECS["irsol"]

# SDO image query/display parameters
FOV_ARCSEC = 400  # field of view for each subplot (arcsec × arcsec)
JSOC_BASE_URL = "http://jsoc.stanford.edu"

# DRMS query keys required for building SunPy maps
DRMS_KEYS = [
    "T_REC",
    "WAVELNTH",
    "CUNIT1",
    "CUNIT2",
    "CTYPE1",
    "CTYPE2",
    "CRPIX1",
    "CRPIX2",
    "CDELT1",
    "CDELT2",
    "CRVAL1",
    "CRVAL2",
    "DSUN_OBS",
    "CRLN_OBS",
    "CRLT_OBS",
    "DATE-OBS",
    "RSUN_OBS",
    "MISSVALS",
]

# SDO data products to fetch: (series, wavelengths, segment, time_format)
SDO_DATA_PRODUCTS = [
    ("aia.lev1_uv_24s", [1600], "image", "%Y-%m-%dT%H:%M:%SZ"),
    ("aia.lev1_euv_12s", [131, 193, 304], "image", "%Y-%m-%dT%H:%M:%SZ"),
    ("hmi.Ic_45s", [6173], "continuum", "%Y.%m.%d_%H:%M:%S_TAI"),
    ("hmi.M_45s", [6173], "magnetogram", "%Y.%m.%d_%H:%M:%S_TAI"),
]

# Display labels matching the order of (series, wavelength) pairs above
SDO_DATA_LABELS = [
    "AIA 1600",
    "AIA 131",
    "AIA 193",
    "AIA 304",
    "HMI Continuum",
    "HMI Magnetogram",
]

# Maximum number of missing pixel values (MISSVALS) allowed in an SDO image
MAX_MISSING_PIXELS = 5000
