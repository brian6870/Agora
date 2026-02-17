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
echo "🔍 Checking if database needs seeding..."
python manage.py shell -c "
from apps.accounts.models import User
import sys
if User.objects.count() == 0:
    print('🌱 Database empty - running seed script...')
    exec(open('scripts/seed_production_data.py').read())
else:
    print(f'📊 Database has {User.objects.count()} users - skipping seed')
"

# Collect static files
# Add this before collecting static files
echo "📁 Creating static directories..."
mkdir -p static/css static/js static/images
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