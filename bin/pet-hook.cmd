@echo off
setlocal
set "PET_HOOK_SCRIPT=%~dp0pet_hook.py"
set "PET_HOOK_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if exist "%PET_HOOK_PYTHON%" (
    "%PET_HOOK_PYTHON%" "%PET_HOOK_SCRIPT%" %*
) else (
    py -3 "%PET_HOOK_SCRIPT%" %*
)
exit /b %errorlevel%
