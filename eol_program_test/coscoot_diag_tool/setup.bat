@echo off
set Cur_path=%~dp0

echo This will install requirements for application.
timeout 3 >nul

if exist yourfoldername\ (
  echo Virtual environment already exists
) else (
  echo Setting up virtual environment
  python.exe -m venv venv
)

echo Installing requirements

"%~dp0\venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0\venv\Scripts\python.exe" -m pip install -r requirements.txt

echo All done.
timeout 3 >nul
