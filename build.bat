@echo off
chcp 65001 > nul
title Build Anhiu OCR - Standalone Package (.exe)
echo ========================================================
echo        BẮT ĐẦU ĐÓNG GÓI ANHIU OCR THÀNH .EXE ĐỘC LẬP
echo ========================================================
echo.

if not exist "app_icon.ico" (
    echo [1/3] Đang tạo icon ứng dụng app_icon.ico...
    python create_icon.py
) else (
    echo [1/3] Đã tìm thấy app_icon.ico.
)

echo.
echo [2/3] Đang chạy PyInstaller build gói AnhiuOCR (có thể mất 1-3 phút)...
python -m PyInstaller --noconfirm --clean anhiu.spec

if errorlevel 1 (
    echo.
    echo [!] CÓ LỖI XẢY RA TRONG QUÁ TRÌNH BUILD!
    pause
    exit /b 1
)

echo.
echo [3/3] Đóng gói thành công!
echo Thư mục kết quả: dist\AnhiuOCR\
echo File thực thi: dist\AnhiuOCR\AnhiuOCR.exe
echo.
echo ========================================================
echo  Bạn có thể nén thư mục "dist\AnhiuOCR" thành file .zip
echo  hoặc dùng Inno Setup để tạo file cài đặt Installer.
echo ========================================================
pause
