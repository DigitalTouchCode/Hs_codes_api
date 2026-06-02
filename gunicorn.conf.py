import os
from decouple import config

bind = "0.0.0.0:8001"

workers = int(config("GUNICORN_WORKERS", "3"))

timeout = 120

accesslog = "-"
errorlog = "-"
