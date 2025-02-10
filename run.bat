@echo off

call .\venv\Scripts\activate

:: Delete all files and subdirectories in the ./coding/ folder
if exist ".\coding\" (
    del /q .\coding\* 2>nul
    for /d %%d in (.\coding\*) do rmdir /s /q "%%d"
)


start cmd /k uvicorn src.api:app --host 0.0.0.0 --port 5000
start cmd /k celery -A src.tasks worker --loglevel=INFO --pool=solo -n multiagent
start cmd /k streamlit run .\app.py

:: Start Redis in WSL
start cmd /k wsl -e sudo service redis-server start

exit
