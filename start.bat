@echo off
REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Install requirements if requirements.txt exists
if exist requirements.txt (
    echo Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
)

REM Start the Python application
echo Starting the program...
python main.py
pause
REM Deactivate virtual environment after program closes
echo Deactivating virtual environment...
deactivate
