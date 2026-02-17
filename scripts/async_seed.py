import os
import sys
import django
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agora_backend.settings')
django.setup()

from apps.accounts.models import User

async def seed_if_needed():
    """Seed database if empty without blocking"""
    if not await sync_to_async(User.objects.filter(tsc_number='SUPER001').exists)():
        print("🌱 Database empty - seeding in background...")
        import subprocess
        subprocess.Popen(
            ["python", "scripts/seed_production_data.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    else:
        print("✅ Database already has users")

if __name__ == "__main__":
    asyncio.run(seed_if_needed())