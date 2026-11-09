#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py setup_company_roles
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 1 --threads 4 --timeout 60 --access-logfile -
