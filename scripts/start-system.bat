@echo off
cd /d "%~dp0\.."
echo Starting the Epicure system (Fast Start)...
echo This will use the previously built images.
docker compose up -d
echo.
echo System is starting up in the background!
echo You can access the website at http://epicure.localhost
pause
