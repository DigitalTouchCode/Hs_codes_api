from .base import *
import dj_database_url
from decouple import config

DEBUG = config("DEBUG", cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

# dbs
DATABASE_URL = config("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")

DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}

# CORSs
CORS_ALLOWED_ORIGINS = []

# Disable rate limiting locallu
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/minute",
        "user": "10000/minute",
    },
}
