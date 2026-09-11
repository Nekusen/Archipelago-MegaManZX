@echo off
rem Launches the VISUAL LOGIC EDITOR (tools/logic_editor/serve.py) and opens the
rem browser at http://127.0.0.1:8765/. Keep this window open while you use the
rem editor; close it (or Ctrl+C) to stop the server.
rem Inside the lab (worlds/mmzx/ as a submodule) it uses the lab's venv Python
rem and the renders from work/room_renders; standalone, it uses the python from
rem the PATH and the local renders from tools/logic_editor/local/renders.
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
