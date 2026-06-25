@echo off
REM copilot-wrap launcher (Windows). Generates & opens your Copilot Wrapped.
setlocal
set "HERE=%~dp0"
where py >nul 2>nul && (set "PY=py") || (set "PY=python")
%PY% "%HERE%..\scripts\wrap.py" %*
endlocal
