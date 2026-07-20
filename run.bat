@echo off
REM Launch the Multi-Agent Chatbot stack on Windows.
REM
REM Redis runs as a systemd service inside WSL (default on Ubuntu-based WSL
REM distros when you `sudo apt install redis-server`). However, Windows' WSL2
REM auto-shuts down the VM after a short idle period when no wsl.exe process
REM is attached -- which kills Redis with it. To prevent that we open a
REM dedicated "WSL keep-alive" window that runs `sleep infinity` inside WSL,
REM keeping the VM (and therefore Redis) alive for the whole session.
REM Close that window to shut the stack down.
REM
REM If redis-server isn't installed/running:
REM     wsl -e sudo apt install -y redis-server
REM     wsl -e sudo systemctl enable --now redis-server

call .\venv\Scripts\activate

echo [1/5] Keeping WSL alive so systemd-managed Redis stays up...
start "WSL keep-alive" cmd /k wsl -e sh -c "echo WSL is kept alive for Redis. Close this window to stop the stack. && sleep infinity"
timeout /t 3 /nobreak >nul

echo [2/5] Verifying Redis...
for /f "delims=" %%R in ('wsl -e redis-cli -p 6379 ping 2^>nul') do set REDIS_PING=%%R
if not "%REDIS_PING%"=="PONG" (
    echo.
    echo   ERROR: Redis is not responding on localhost:6379.
    echo   Start it with:  wsl -e sudo systemctl start redis-server
    echo.
    pause
    exit /b 1
)
echo   Redis OK (PONG)

echo [3/5] Starting FastAPI (port 5000)...
start "API"       cmd /k uvicorn src.api:app --host 0.0.0.0 --port 5000

echo [4/5] Starting Celery worker...
start "Celery"    cmd /k celery -A src.tasks worker --loglevel=INFO --pool=solo -n multiagent

echo [5/5] Starting Streamlit UI...
start "Streamlit" cmd /k streamlit run .\app.py

echo.
echo All services launched. Close the spawned terminals to stop each service.
exit
