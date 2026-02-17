#!/bin/bash
echo "🚀 Starting Agora Voting System on Render..."
echo "==========================================="

# Debug information
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "PORT: $PORT"

# Set Django settings module (use production settings)
export DJANGO_SETTINGS_MODULE=agora_backend.settings

# Run database migrations FIRST (critical)
echo "📦 Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "==========================================="
echo "✅ Starting Gunicorn on port $PORT..."
echo "==========================================="

# Start Gunicorn
exec gunicorn agora_backend.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -