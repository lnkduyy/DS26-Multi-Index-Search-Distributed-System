@echo off
echo Shutting down old containers and rebuilding the system...
docker-compose down
docker-compose up -d --build
echo.
echo Rebuild complete and system is starting up!
echo You can access the website at http://epicure.localhost
pause
