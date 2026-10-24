@echo off
rem Downloads today's race card and results. Windows Task Scheduler runs this.
cd /d "%~dp0"
if not exist racing\data mkdir racing\data
echo ==== %date% %time% >> racing\data\log.txt
.venv\Scripts\python.exe -m racing.results >> racing\data\log.txt 2>&1
