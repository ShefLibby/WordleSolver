@echo off
echo ============================================
echo  Wordle Solver -- EXE Build Script
echo ============================================

echo.
echo [1/3] Installing dependencies...
pip install --upgrade selenium webdriver-manager pyinstaller
if %ERRORLEVEL% neq 0 (
    echo ERROR: pip install failed. Make sure Python is installed and in PATH.
    pause
    exit /b 1
)

echo.
echo [2/3] Building exe with PyInstaller...
python -m PyInstaller ^
    --onefile ^
    --name WordleSolver ^
    --add-data "words.txt;." ^
    --hidden-import selenium ^
    --hidden-import webdriver_manager ^
    --hidden-import webdriver_manager.chrome ^
    main.py
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo Output: dist\WordleSolver.exe
echo.
pause
