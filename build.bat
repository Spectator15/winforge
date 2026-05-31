@echo off
echo ============================================
echo   WinForge Build Script
echo ============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Install dependencies if needed
echo [1/4] Installing dependencies...
pip install customtkinter pyinstaller --quiet
echo Done.
echo.

:: Clean old build
echo [2/4] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist WinForge.spec del WinForge.spec
echo Done.
echo.

:: Build exe
echo [3/4] Building WinForge.exe...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name WinForge ^
    --uac-admin ^
    --add-data "ui;ui" ^
    --add-data "core;core" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    main.py

echo.

:: Check result
if exist dist\WinForge.exe (
    echo [4/4] Build successful!
    echo.
    echo Output: dist\WinForge.exe
    echo.
    echo You can now run WinForge.exe directly. It will auto-request admin rights.
) else (
    echo [ERROR] Build failed. Check the output above for errors.
)

echo.
pause
