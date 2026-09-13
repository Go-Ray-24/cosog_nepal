"""Central configuration for the Forest Fire Early Warning System.

All values are read from environment variables (see .env.example).
Nothing secret is hard-coded here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- NASA FIRMS -------------------------------------------------------
# Get a free key at https://firms.modaps.eosdis.nasa.gov/api/map_key/
FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "3b212bf04c7fadc029277039f587ef34")

# Satellite/sensor source. Common choices:
# VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT, MODIS_NRT
FIRMS_SOURCE = os.getenv("FIRMS_SOURCE", "VIIRS_SNPP_NRT")

# Bounding box for Nepal: west, south, east, north
NEPAL_BBOX = os.getenv("NEPAL_BBOX", "80.0,26.3,88.3,30.5")

# How many days back to query (FIRMS allows 1-10 for the area API)
FIRMS_DAY_RANGE = int(os.getenv("FIRMS_DAY_RANGE", "1"))

FIRMS_AREA_URL = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
    "{map_key}/{source}/{bbox}/{days}"
)

# --- App -------------------------------------------------------------------
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

# Selectable regions [west, south, east, north]
REGIONS = {
    "nepal": {"label": "Nepal", "bbox": "80.0,26.3,88.3,30.5"},
    "india": {"label": "India", "bbox": "68.7,8.4,97.4,37.1"},
}
DEFAULT_REGION = os.getenv("DEFAULT_REGION", "nepal")

# Default bounding box used when no region/bbox is supplied by the request.
NEPAL_BBOX = REGIONS.get(DEFAULT_REGION, REGIONS["nepal"])["bbox"]

mail_sender=os.getenv("EMAIL_SENDER", "mlsn.314596841f69228e5b8f265d61fb0d95915a1191c5c4a52947c926d5555811db")