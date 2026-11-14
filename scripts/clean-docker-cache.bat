@echo off
echo Cleaning up Docker build cache to free up disk space...
docker builder prune -f
echo.
echo Cleanup complete!
pause
