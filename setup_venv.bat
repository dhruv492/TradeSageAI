@echo off
cd C:\Users\dcpat\OneDrive\Desktop\ML\Project_1\Project\TradeSageAI

:: Create fresh virtualenv
if exist /tmp/tradesage_venv rmdir /S /Q /tmp/tradesage_venv
python -m venv /tmp/tradesage_venv

:: Activate and install
call /tmp/tradesage_venv/Scripts/activate
pip install --upgrade pip >NUL 2>&1

echo Installing requirements...
pip install -r backend\requirements.txt 2>&1
echo Install complete.