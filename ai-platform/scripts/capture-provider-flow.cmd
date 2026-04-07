@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0assert-canonical-repo.ps1"
if errorlevel 1 exit /b 1
set "ROOT=%~dp0.."
pushd "%ROOT%\frontend" || (
  echo Failed to enter frontend directory
  exit /b 1
)
node scripts\capture-provider-full-flow.mjs
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

