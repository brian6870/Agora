@echo off
echo ========================================
echo Agora Voting - ULTIMATE FIX SCRIPT
echo ========================================
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

echo Step 1: Reinstalling Django...
echo.
pip uninstall django -y
pip install django==4.2.7

echo.
echo Step 2: Fixing manage.py...
echo.

(
echo #!/usr/bin/env python
echo import os
echo import sys
echo.
echo def main(^):
echo     os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agora_backend.settings')
echo     try:
echo         from django.core.management import execute_from_command_line
echo     except ImportError as exc:
echo         raise ImportError(
echo             "Couldn't import Django. Are you sure it's installed?"
echo         ) from exc
echo     execute_from_command_line(sys.argv^)
echo.
echo if __name__ == '__main__':
echo     main(^)
) > manage.py.new

move /y manage.py.new manage.py >nul
echo ✅ Fixed manage.py

echo.
echo Step 3: Fixing wsgi.py...
echo.

(
echo import os
echo import sys
echo.
echo path = os.path.dirname(os.path.dirname(os.path.abspath(__file__^)^)^)
echo if path not in sys.path:
echo     sys.path.append(path^)
echo.
echo os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agora_backend.settings'^)
echo.
echo from django.core.wsgi import get_wsgi_application
echo application = get_wsgi_application(^)
) > agora_backend\wsgi.py.new

move /y agora_backend\wsgi.py.new agora_backend\wsgi.py >nul
echo ✅ Fixed wsgi.py

echo.
echo Step 4: Fixing __init__.py...
echo.

echo # This file makes the directory a Python package > agora_backend\__init__.py
echo ✅ Fixed __init__.py

echo.
echo Step 5: Verifying Django installation...
echo.

python -c "import django; print(f'Django version: {django.get_version()}')"

echo.
echo Step 6: Testing WSGI import...
echo.

python -c "from agora_backend.wsgi import application; print('✅ WSGI import successful')" 2>nul
if %errorlevel% equ 0 (
    echo ✅ WSGI import test passed
) else (
    echo ❌ WSGI import test failed
    python -c "import agora_backend.wsgi; print('Module imported but no application?')" 2>nul
)

echo.
echo Step 7: Testing Django check...
echo.

python manage.py check

echo.
echo ========================================
echo FIX COMPLETE!
echo ========================================
echo.
echo Now run: python manage.py runserver
echo.
pause