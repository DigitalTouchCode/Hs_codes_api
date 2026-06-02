import os

bind = "0.0.0.0:8001"

workers = int(os.getenv("GUNICORN_WORKERS", "3"))

timeout = 120

accesslog = "-"
errorlog = "-"
