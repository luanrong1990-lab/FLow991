@echo off
title VQPVEO3PRO - AI Video Studio
color 0A

:: Chuyển đến thư mục chứa file bat (để đảm bảo đường dẫn luôn đúng)
cd /d "%~dp0"

echo ===================================================
echo     VQPVEO3PRO - AI VIDEO GENERATION STUDIO
echo ===================================================
echo.
echo Dang khoi dong he thong... Vui long doi giay lat!
echo.

:: Chạy ứng dụng bằng Python
python app\main.py

:: Tạm dừng màn hình nếu có lỗi xảy ra để người dùng kịp đọc
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Chuong trinh da gap loi va thoat dot ngot.
    pause
)
