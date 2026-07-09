#!/usr/bin/env bash
# Render/Railway build step for the backend.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py seed_fx
