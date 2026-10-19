@echo off
echo ========================================================
echo       CloudLibrary - Automated GitHub Push Helper
echo ========================================================
echo.

set /p REPO_URL="Apna GitHub Repository URL paste karein (e.g. https://github.com/username/cloud-library.git): "

if "%REPO_URL%"=="" (
    echo.
    echo [ERROR] Repository URL khali nahi ho sakta!
    pause
    exit /b
)

echo.
echo [*] 1. Initializing Git repository...
git init

echo [*] 2. Staging project files...
git add .

echo [*] 3. Committing project code...
git commit -m "Initial commit: CloudLibrary system with AWS deployment scripts and Neumorphic UI"

echo [*] 4. Setting branch to main...
git branch -M main

echo [*] 5. Configuring remote origin...
git remote remove origin 2>nul
git remote add origin %REPO_URL%

echo [*] 6. Pushing to GitHub...
git push -u origin main

echo.
echo ========================================================
echo [SUCCESS] Code successfully pushed to GitHub!
echo ========================================================
pause
