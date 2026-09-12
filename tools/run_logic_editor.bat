@echo off
rem Starts the visual logic editor and opens http://127.0.0.1:8765/ in the browser.
rem Close this window or press Ctrl+C to stop the server.
rem Inside a parent checkout with a .venv, its Python and its work/room_renders are used.
cd /d "%~dp0.."
set LAB=%~dp0..\..\..
if exist "%LAB%\.venv\Scripts\python.exe" (
  echo Logic editor: http://127.0.0.1:8765/  ^(close this window to stop^)
  "%LAB%\.venv\Scripts\python.exe" tools\logic_editor\serve.py --port 8765 --renders "%LAB%\work\room_renders"
) else (
  echo Logic editor: http://127.0.0.1:8765/  ^(close this window to stop^)
  python tools\logic_editor\serve.py --port 8765
)
pause
