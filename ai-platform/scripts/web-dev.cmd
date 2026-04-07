@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0assert-canonical-repo.ps1"
if errorlevel 1 exit /b 1
set "ROOT=%~dp0.."
pushd "%ROOT%\frontend" || (
  echo Failed to enter frontend directory
  exit /b 1
)
npm.cmd run dev -- --host 127.0.0.1 --port 5174
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

