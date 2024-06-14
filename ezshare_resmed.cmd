@echo off
SETLOCAL

SET venv_name=%USERPROFILE%\.venv\ezshare_resmed
SET script_dir=%~dp0

CALL :check_venv %venv_name%,venv_exists

IF %venv_exists%==0 (
    echo "%venv_name% is not present. Run install.bat to setup environment"
)
"%venv_name%\Scripts\python" %script_dir%ezshare_resmed.py %*

EXIT /B %ERRORLEVEL%

:check_venv
IF EXIST "%~1\" (
    SET /A %~2=1
) ELSE (
    SET  /A %~2=0
)
EXIT /B 0
