@echo off
cd /d %~dp0

:: ============================================================
::  release_main.bat - rilis development -> main (tanpa PR)
::
::  Cara kerja: main di-fast-forward ke development lewat
::  "git push origin development:main". Tidak ada checkout, jadi
::  file lokal yang berubah tidak terganggu.
::
::  Syarat:
::    - sedang di branch development
::    - commit_session.bat sudah dijalankan (tag versi sudah ada)
::    - kalau main punya commit yang tidak ada di development, script
::      me-merge origin/main ke development dulu (batal otomatis bila konflik)
::
::  Script ini PUSH (setelah konfirmasi y). Dijalankan oleh user,
::  tidak pernah oleh Claude.
:: ============================================================

if exist .git\index.lock del /f .git\index.lock

for /f %%b in ('git branch --show-current') do set "BR=%%b"
if not "%BR%"=="development" ( echo GAGAL: harus di branch development, sekarang di %BR%. & goto :end )

set "VER="
for /f "tokens=3" %%a in ('findstr /b "APP_VERSION" app\_constants.py') do set "VER=%%~a"
if "%VER%"=="" ( echo GAGAL: APP_VERSION tidak terbaca dari app\_constants.py. & goto :end )
set "TAG=v%VER%"

echo Mengambil data terbaru dari origin...
git fetch origin --tags
if errorlevel 1 ( echo GAGAL: git fetch. & goto :end )

:: tag versi harus ada dan sudah termasuk di HEAD (commit_session.bat sudah jalan)
set "TAGSHA="
for /f %%h in ('git rev-parse -q --verify %TAG%^^{commit}') do set "TAGSHA=%%h"
if "%TAGSHA%"=="" (
    echo GAGAL: tag %TAG% belum ada. Jalankan commit_session.bat dulu.
    goto :end
)
git merge-base --is-ancestor %TAG% HEAD
if errorlevel 1 ( echo GAGAL: tag %TAG% bukan bagian dari HEAD. & goto :end )

for /f %%h in ('git rev-parse HEAD') do set "HEADSHA=%%h"

:: kalau main punya commit yang tidak ada di development, sinkronkan dulu
set "SYNC="
git merge-base --is-ancestor origin/main HEAD
if errorlevel 1 set "SYNC=1"

echo.
echo Versi / tag : %TAG%
echo Commit      : %HEADSHA:~0,7%
echo Yang akan masuk ke main:
git log --oneline origin/main..HEAD
echo.
echo Akan dijalankan:
if defined SYNC echo    git merge origin/main   (main punya commit baru, disinkronkan ke development dulu)
echo    git push origin development
echo    git push origin development:main
echo    git push origin %TAG%
echo.
set /p OK=Lanjut rilis %TAG% ke main? [y/N]: 
if /i not "%OK%"=="y" ( echo Dibatalkan. & goto :end )

if defined SYNC (
    git merge origin/main --no-edit -m "merge: sinkron main ke development sebelum rilis %TAG%"
    if errorlevel 1 (
        git merge --abort
        echo GAGAL: konflik saat merge main. Dibatalkan, tidak ada yang berubah/di-push.
        goto :end
    )
)

git push origin development || goto :fail
git push origin development:main || goto :fail
git push origin %TAG% || goto :fail

echo.
echo === Rilis %TAG% selesai: main = development ===
goto :end

:fail
echo.
echo GAGAL saat push. Cek pesan di atas, tidak ada yang dipaksa (tanpa --force).

:end
echo.
pause
