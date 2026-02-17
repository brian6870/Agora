#!/bin/bash
echo "🚀 Starting Agora Voting System on Render..."
echo "==========================================="

# Print current directory
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la

# Run diagnostic
echo "==========================================="
echo "🔍 Running diagnostic..."
python scripts/diagnose.py
echo "==========================================="

# Set Python path explicitly
export PYTHONPATH="/opt/render/project/src:$PYTHONPATH"
echo "PYTHONPATH set to: $PYTHONPATH"

# Set Django settings module
export DJANGO_SETTINGS_MODULE=agora_backend.settings_production
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"

# Run migrations
echo "📦 Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Check if we need to seed
echo "🔍 Checking if database needs seeding..."
python manage.py shell -c "
from apps.accounts.models import User
if User.objects.count() == 0:
    print('🆕 Empty database - will seed')
    exit(0)
else:
    print(f'📊 Database has {User.objects.count()} users - skipping seed')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "🌱 Seeding database..."
    python scripts/seed_production_data.py
fi

echo "==========================================="
echo "✅ Starting Gunicorn..."
echo "==========================================="

# Try different Gunicorn commands
echo "Attempt 1: Standard gunicorn command"
gunicorn agora_backend.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --access-logfile - \
    --error-logfile - \
    --pythonpath /opt/render/project/src

# If that fails, this line won't be reached