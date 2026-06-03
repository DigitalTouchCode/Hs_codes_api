#!/bin/sh

set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --config gunicorn.conf.py
