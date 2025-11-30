@echo off
echo 🚀 Installing AlphaStack...

REM Check if pip is installed
where pip >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ pip could not be found. Please install Python and pip first.
    pause
    exit /b 1
)

REM Install the package
echo 📦 Installing dependencies and package...
pip install .

if %errorlevel% equ 0 (
    echo.
    echo ✅ Installation complete!
    echo 🎉 You can now run 'alphastack' in any terminal.
) else (
    echo ❌ Installation failed. Please check the errors above.
)

pause

