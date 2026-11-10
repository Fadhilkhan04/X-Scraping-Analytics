@echo off
set /p USERNAME=Enter public X username (without @):
set /p COUNT=Number of posts (default 100):
if "%COUNT%"=="" set COUNT=100
python scraper.py %USERNAME% --max-posts %COUNT%
pause
