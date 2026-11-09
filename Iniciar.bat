@echo off
REM Desk Stickmen - doble clic para arrancar
cd /d "%~dp0"
where python >nul 2>nul || (echo No encontre Python. Instalalo desde https://www.python.org y marca "Add to PATH". & pause & exit /b 1)
python -c "import PySide6" >nul 2>nul || (echo Instalando PySide6 por unica vez... & python -m pip install -r requirements.txt || (pause & exit /b 1))
where pythonw >nul 2>nul && (start "" pythonw desk_stickmen.py) || (start "" python desk_stickmen.py)
