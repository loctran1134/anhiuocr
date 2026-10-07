@echo off
cd /d "%~dp0"
chcp 65001 > nul
title Anhiu - Đếm điểm bán tự động
echo Đang khởi chạy phần mềm Anhiu...
set PYTHON_EXEC=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXEC=.venv\Scripts\python.exe
)
%PYTHON_EXEC% app_window.py
