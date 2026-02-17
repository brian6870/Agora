
# deployment/deploy.sh
#!/bin/bash

# Agora Voting Platform Deployment Script

set -e

echo "🚀 Starting Agora Voting Platform Deployment"

# Load environment variables
source .env.production

# Update code
echo "📦 Pulling latest code..."
git pull origin main

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "🗄️ Running database migrations..."
python manage.py migrate

# Collect static files
echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

# Create cache table
python manage.py createcachetable

# Run tests
echo "🧪 Running tests..."
python manage.py test

# Backup database
echo "💾 Creating database backup..."
cp agora.db "backups/agora_$(date +%Y%m%d_%H%M%S).db"

# Restart services
echo "🔄 Restarting services..."
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# Verify deployment
echo "✅ Verifying deployment..."
curl -f https://voting.agora.ke || exit 1

echo "✅ Deployment complete! Application is live at https://voting.agora.ke"

# Monitor logs
echo "📋 Tailing logs (Ctrl+C to exit)..."
sudo journalctl -u gunicorn -f