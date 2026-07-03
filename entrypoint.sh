#!/bin/sh

set -e

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-core.settings.production}"

echo "Using settings: $DJANGO_SETTINGS_MODULE"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn..."
exec gunicorn core.wsgi:application \
    --config gunicorn.conf.py
