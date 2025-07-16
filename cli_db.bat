::  cli_db.bat  ---------------------------------------------
@echo off
REM Run the CLI entry‑point and forward all cmd‑line args.
REM If you have your virtual‑env activated, plain `python` will
REM already resolve to .venv\Scripts\python.exe.

python -m pentest_bot.cli_db.cli_db %*
