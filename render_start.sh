#!/bin/bash
echo "🚀 Starting Agora with parallel seeding..."

# Start Gunicorn IMMEDIATELY in the background
gunicorn agora_backend.wsgi:application --bind 0.0.0.0:$PORT --daemon
echo "✅ Gunicorn started in background on port $PORT"

# Give it a moment to bind
sleep 2

# Check if port is bound
if netstat -tln | grep -q ":$PORT"; then
    echo "✅ Port $PORT is bound - server is running"
else
    echo "⚠️ Port not bound yet, but Gunicorn is starting..."
fi

# Run migrations (non-blocking)
echo "📦 Running migrations in background..."
python manage.py migrate --noinput &

# Check and seed if needed
echo "🔍 Checking database..."
python manage.py shell -c "
from apps.accounts.models import User
if not User.objects.filter(tsc_number='SUPER001').exists():
    print('🌱 Seeding database in background...')
    import subprocess
    subprocess.Popen(['python', 'scripts/seed_production_data.py'])
else:
    print('✅ Database already has users')
"

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput &

# Keep the script running
echo "==========================================="
echo "✅ All services started. Monitoring..."
echo "==========================================="

# Wait forever (or until interrupted)
while true; do
    sleep 60
done