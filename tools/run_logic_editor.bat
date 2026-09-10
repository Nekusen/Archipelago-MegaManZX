@echo off
rem Lanza el EDITOR VISUAL DE LOGICA (tools/logic_editor/serve.py) y abre el
rem navegador en http://127.0.0.1:8765/. Deja esta ventana abierta mientras uses
rem el editor; cierrala (o Ctrl+C) para parar el servidor.
rem Dentro del laboratorio (worlds/mmzx/ como submodulo) usa el Python del venv
rem del laboratorio y los renders de work/room_renders; suelto, usa el python
rem del PATH y los renders locales de tools/logic_editor/local/renders.
cd /d "%~dp0.."
set LAB=%~dp0..\..\..
if exist "%LAB%\.venv\Scripts\python.exe" (
  echo Editor de logica: http://127.0.0.1:8765/  ^(cierra esta ventana para parar^)
  "%LAB%\.venv\Scripts\python.exe" tools\logic_editor\serve.py --port 8765 --renders "%LAB%\work\room_renders"
) else (
  echo Editor de logica: http://127.0.0.1:8765/  ^(cierra esta ventana para parar^)
  python tools\logic_editor\serve.py --port 8765
)
pause
