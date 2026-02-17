#!/bin/bash
# Render.com start script

echo "🚀 Starting Agora Voting System on Render..."
echo "==========================================="

# Print environment info
echo "Python version: $(python --version)"
echo "Django version: $(python -m django --version)"
echo "Working directory: $(pwd)"
echo "==========================================="

# Run database migrations
echo "📦 Running database migrations..."
python manage.py migrate --noinput

# Check if we need to seed the database
echo "🔍 Checking if database needs seeding..."
python manage.py shell -c "
from apps.accounts.models import User
if User.objects.count() == 0:
    print('🆕 Empty database detected - will seed...')
    exit(0)
else:
    print(f'📊 Database already has {User.objects.count()} users - skipping seed')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "🌱 Seeding database with initial data..."
    python scripts/seed_production_data.py
else
    echo "✅ Database already populated - skipping seed"
fi

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist (fallback)
echo "👑 Ensuring superuser exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        email='admin@agora.ke',
        password='Admin@2026',
        full_name='System Admin',
        tsc_number='ADMIN001',
        id_number='30000000'
    )
    print('✅ Superuser created')
"

echo "==========================================="
echo "✅ Startup complete! Starting Gunicorn server..."
echo "==========================================="

# Start Gunicorn
exec gunicorn --bind 0.0.0.0:$PORT --workers 4 --threads 2 --timeout 120 --access-logfile - --error-logfile - agora_backend.wsgi:application