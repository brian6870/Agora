#!/bin/bash
echo "🚀 Starting Agora on Render..."

# Run migrations
python manage.py migrate --noinput

# RUN SEED SCRIPT DIRECTLY (regardless of user count)
echo "🌱 Running seed script..."
python scripts/seed_production_data.py

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
exec gunicorn agora_backend.wsgi:application --bind 0.0.0.0:$PORT