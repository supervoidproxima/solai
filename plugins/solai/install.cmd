@echo off
rem Solai - the same one-liner the page shows, in a file that can be double-clicked.
rem
rem It is deliberately this short. A downloaded script is a larger thing to trust than a line
rem of text somebody can read, so this one does nothing of its own: it prints the command it
rem is about to run, runs it in PowerShell, and waits at the end so the window does not
rem vanish over whatever the installer had to say.
rem
rem Everything that matters is in install.ps1, next to this file in the same repository.
setlocal
set "SOLAI_URL=https://raw.githubusercontent.com/supervoidproxima/solai/main/install.ps1"

echo Solai installer.
echo.
echo   This window is about to run:
echo     irm %SOLAI_URL% ^| iex   %*
echo.
echo   Ctrl+C now if that is not what you want.
echo.

rem Arguments are passed through, so the flags the page documents work here too:
rem   install.cmd -SkipApps        install.cmd -CloseWhenDone        install.cmd -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm '%SOLAI_URL%'))) %*"
set "CODE=%ERRORLEVEL%"

echo.
if not "%CODE%"=="0" echo The installer exited with code %CODE%. Nothing above was skipped quietly: read the last stage it reported.
echo Press any key to close this window.
pause >nul
endlocal
