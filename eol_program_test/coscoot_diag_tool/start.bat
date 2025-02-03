@echo off
echo Start application
set Cur_path=%~dp0
"%Cur_path%\venv\Scripts\python.exe" run.py %* || (
  pause
)
