#!/usr/bin/env python
"""
Diagnostic script to check Python path and project structure on Render
Run this in your render_start.sh before starting gunicorn
"""

import os
import sys
import django

print("="*60)
print("🔍 DIAGNOSTIC INFORMATION")
print("="*60)

# Check current directory
print(f"\n📁 Current directory: {os.getcwd()}")
print(f"📁 Directory contents:")
for item in os.listdir('.'):
    if os.path.isdir(item):
        print(f"  📂 {item}/")
    else:
        print(f"  📄 {item}")

# Check Python path
print(f"\n🐍 Python path:")
for i, path in enumerate(sys.path, 1):
    print(f"  {i}. {path}")

# Check if agora_backend is accessible
print(f"\n🔎 Checking module imports:")
try:
    import agora_backend
    print(f"  ✅ agora_backend found at: {agora_backend.__file__}")
except ImportError as e:
    print(f"  ❌ Cannot import agora_backend: {e}")

try:
    from agora_backend import settings
    print(f"  ✅ settings module found")
    print(f"  📋 DEBUG: {getattr(settings, 'DEBUG', 'Not set')}")
    print(f"  📋 ALLOWED_HOSTS: {getattr(settings, 'ALLOWED_HOSTS', 'Not set')}")
except ImportError as e:
    print(f"  ❌ Cannot import settings: {e}")

# Check apps
print(f"\n📦 Checking apps:")
apps_to_check = ['accounts', 'core', 'voting', 'admin_panel']
for app in apps_to_check:
    try:
        __import__(f'apps.{app}')
        print(f"  ✅ apps.{app} found")
    except ImportError:
        try:
            __import__(app)
            print(f"  ✅ {app} found (as top-level)")
        except ImportError:
            print(f"  ❌ Cannot import {app}")

# Check manage.py
print(f"\n🛠️  Checking manage.py:")
if os.path.exists('manage.py'):
    print(f"  ✅ manage.py exists")
else:
    print(f"  ❌ manage.py not found!")

print("\n" + "="*60)
print("✅ Diagnostic complete")
print("="*60)