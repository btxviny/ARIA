@echo off

call .\venv\Scripts\activate

start cmd /k uvicorn src.api:app --host 0.0.0.0 --port 5000
start cmd /k celery -A src.tasks worker --loglevel=INFO --pool=solo -n multiagent
start cmd /k streamlit run .\app.py

:: Start Redis in WSL as background daemon
wsl -e sh -lc "redis-server --daemonize yes"

exit
