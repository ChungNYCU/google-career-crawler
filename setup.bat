@echo off

REM Define the name of the virtual environment
set ENV_NAME=venv

REM Create virtual environment
python -m venv %ENV_NAME%

REM Activate virtual environment
call %ENV_NAME%\Scripts\activate

REM Check if requirements.txt exists and install requirements
if exist requirements.txt (
    pip install -r requirements.txt
) else (
    echo requirements.txt does not exist.
)

echo Setup completed. Virtual environment '%ENV_NAME%' is activated.