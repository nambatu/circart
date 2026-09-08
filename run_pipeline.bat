@echo off
echo Running resolve.py...
python resolve.py artline.json
if %errorlevel% neq 0 (
    echo resolve.py failed.
    exit /b %errorlevel%
)

echo.
echo Running fetch_images.py...
python fetch_images.py artline.json
if %errorlevel% neq 0 (
    echo fetch_images.py failed.
    exit /b %errorlevel%
)

echo.
echo Pipeline finished successfully.
