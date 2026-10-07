@echo off
chcp 65001 > nul
echo ========================================================
echo        ReconAuto.ID - Auto Push ke GitHub
echo ========================================================
echo.

:: 1. Cek apakah Git sudah terpasang
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [PERINGATAN] Git belum terdeteksi di sistem Anda.
    echo Untuk menginstalnya otomatis, buka PowerShell dan ketik:
    echo     winget install --id Git.Git -e --source winget
    echo.
    pause
    exit /b 1
)

:: 2. Inisialisasi git jika belum ada folder .git
if not exist ".git" (
    echo [1/4] Menginisialisasi repositori Git...
    git init
    git branch -M main
    echo.
    set /p REPO_URL="Masukkan URL GitHub Anda (contoh: https://github.com/USER/NAMA_REPO.git): "
    git remote add origin %REPO_URL%
    echo Repositori terhubung!
    echo.
)

:: 3. Stage file-file inti
echo [2/4] Memilih berkas yang aman diunggah...
git add core templates sample_data main.py requirements.txt Procfile Dockerfile .dockerignore .gitignore Dokumentasi_Lengkap_ReconAuto_ID.pdf rekonsile.db

:: 4. Commit
echo [3/4] Menyimpan perubahan (Commit)...
git commit -m "Auto-deploy ReconAuto.ID: %date% %time%"

:: 5. Push ke GitHub
echo [4/4] Mengunggah (Push) ke GitHub...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo   BERHASIL DIUNGGAH KE GITHUB!
    echo   Render.com akan otomatis memulai deploy dalam 1-2 menit.
    echo ========================================================
) else (
    echo.
    echo [INFO] Jika gagal autentikasi, pastikan Anda sudah login akun GitHub di browser/terminal.
)

echo.
pause
