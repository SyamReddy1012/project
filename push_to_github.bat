@echo off
title Push MPTracker to GitHub (project)
echo ===================================================
echo Pushing Missing Person Tracker to GitHub: project
echo ===================================================
cd /d "C:\Users\Syam Sundar\OneDrive\Desktop\missing-person-tracker"
echo.
echo Current branch and status:
git branch --show-current
git status -s
echo.
echo Connecting to https://github.com/SyamReddy1012/project.git ...
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo ===================================================
    echo [SUCCESS] Pushed to https://github.com/SyamReddy1012/project !
    echo ===================================================
) else (
    echo ===================================================
    echo [NOTICE] If your browser opened GitHub authentication, please authorize it.
    echo ===================================================
)
pause
