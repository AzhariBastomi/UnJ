# CLAUDE.md — Aturan Kerja Repo UnJ

Aturan wajib yang harus diikuti Claude di setiap sesi pada repo ini.

---

## 1. Versioning

Sumber tunggal versi: **`app/_constants.py` → `APP_VERSION`** (saat ini `1.1.0`).
Format: `MAJOR.MINOR.PATCH`.

Di akhir sesi, nilai sendiri perubahan yang dibuat dan **naikkan versinya kalau memenuhi
kriteria di bawah** — tidak perlu tanya dulu. Langsung naikkan, lalu sebutkan alasannya
dalam satu baris.

| Naik ke | Kapan | Contoh di repo ini |
|---|---|---|
| **MAJOR** `2.0.0` | Breaking — yang lama berhenti jalan | schema DB / format `_steps.json` / struktur config berubah tidak kompatibel; command lama dihapus atau signature-nya diubah; sequence test lama gagal dijalankan |
| **MINOR** `1.2.0` | Fitur / fungsi baru, tetap kompatibel ke belakang | command atau ftm baru, mixin baru, field opsional baru di `TestItem`, dukungan device baru, panel UI baru, opsi config baru yang punya default |
| **PATCH** `1.1.1` | Perbaikan tanpa fitur baru | bugfix, tuning timeout/nilai, refactor internal, perbaikan log, docs, typo |

Aturan tambahan:

- **Satu sesi maksimum satu kenaikan.** Kalau dalam satu sesi ada fitur baru *dan* bugfix,
  ambil yang tertinggi saja (MINOR), jangan dua kali naik.
- MINOR naik → PATCH reset ke `0`. MAJOR naik → MINOR dan PATCH reset ke `0`.
- Kalau sesi hanya baca kode, diskusi, atau menjawab pertanyaan **tanpa mengedit file**:
  jangan naikkan versi, dan jangan buat `.bat`.
- Kalau ragu antara PATCH dan MINOR: ada kemampuan baru yang bisa dipakai user → MINOR.
  Tidak ada → PATCH.
- Versi baru ditulis ke `APP_VERSION`, dan file `app/_constants.py` ikut masuk daftar file
  yang di-commit.

---

## 2. Akhir sesi: buat `commit_session.bat`

Setiap sesi yang mengedit file diakhiri dengan menulis/menimpa **`commit_session.bat`** di
root repo. Nama filenya tetap, jadi selalu ketimpa sesi berikutnya (bukan menumpuk).

Isinya wajib memuat tiga hal:

1. **Daftar file yang diedit selama sesi itu** — satu `git add "<path>"` per file.
   Daftarnya hanya file yang benar-benar disentuh di sesi tersebut.
2. **Keterangan commit** — satu baris `TITLE` bergaya Conventional Commit
   (`feat:` / `fix:` / `refactor:` / `docs:` / `chore:`), lalu `LINE1..LINEn` berisi
   penjelasan per perubahan. Satu baris = satu perubahan nyata, sebut nama
   file/fungsinya. Bahasa Indonesia, sesuai gaya commit yang sudah ada.
3. **Perintah commit** — `git commit -F` dari file message sementara, plus `git tag`
   kalau versi naik.

### Yang TIDAK boleh ada di .bat

- **`git add -A` atau `git add .`** — dilarang. Di repo ini ada ratusan file yang
  terlihat *modified* padahal cuma beda line-ending (CRLF vs LF); `add -A` akan
  menyeret semuanya ke dalam commit. Selalu `git add` per file secara eksplisit.
- **`git push`** — push tidak masuk script. Lihat aturan 3. Satu-satunya pengecualian:
  `release_main.bat` (khusus rilis, dijalankan user, ada konfirmasi `y`).

### Template

```bat
@echo off
cd /d %~dp0

:: ============================================================
::  Dibuat otomatis oleh Claude - sesi <YYYY-MM-DD HH:MM>
::  Versi: 1.1.0 -> 1.2.0  (MINOR: <alasan singkat>)
::  Branch: development
::
::  Script ini HANYA commit. Push dilakukan manual oleh user.
::  Periksa isinya dulu, lalu jalankan (double-click).
:: ============================================================

:: ---------- Keterangan commit ----------
set "TITLE=feat: <ringkasan satu baris>"
set "LINE1=- <file/fungsi>: <apa yang berubah dan kenapa>"
set "LINE2=- "
set "LINE3=- "
set "LINE4=- "
set "LINE5=- "

:: Kosongkan TAG kalau versi tidak naik
set "TAG=v1.2.0"

:: ---------- File yang diedit sesi ini ----------
if exist .git\index.lock del /f .git\index.lock

git add "app/_constants.py"
git add "<path/file/kedua>"
git add "<path/file/ketiga>"

:: ---------- Commit ----------
set MSG=%TEMP%\unj_commit_msg.txt
> "%MSG%" echo %TITLE%
>> "%MSG%" echo.
>> "%MSG%" echo %LINE1%
>> "%MSG%" echo %LINE2%
>> "%MSG%" echo %LINE3%
>> "%MSG%" echo %LINE4%
>> "%MSG%" echo %LINE5%

echo === Yang akan di-commit ===
git diff --cached --name-only
echo.

git commit -F "%MSG%"
del "%MSG%"

if not "%TAG%"=="" (
    git tag -a %TAG% -m "%TAG%"
    echo Tag dibuat: %TAG%
)

echo.
echo === Selesai (belum di-push) ===
git log --oneline -3
echo.
echo Untuk push, jalankan manual:
echo    git push origin development
if not "%TAG%"=="" echo    git push origin %TAG%
echo.
pause
```

---

## 3. Claude tidak commit, tidak push

Mutlak, tanpa pengecualian:

- Claude **tidak pernah** menjalankan `git commit`.
- Claude **tidak pernah** menjalankan `git push`.
- Claude juga tidak menjalankan `git tag`, `git reset --hard`, `git rebase`,
  `git checkout <branch>`, atau apa pun yang mengubah riwayat/branch.

Yang boleh dijalankan Claude hanya perintah **baca**: `git status`, `git diff`, `git log`,
`git show`, `git branch`, `git remote -v`.

Claude berhenti di titik "file `commit_session.bat` sudah siap". Keputusan untuk commit
dan push sepenuhnya milik user, dengan menjalankan script itu sendiri.

Kalau user minta Claude commit atau push secara langsung, ingatkan aturan ini dulu dan
minta konfirmasi eksplisit di pesan itu sebelum melakukannya.

---

## 4. Alur Git tim (GitHub Flow)

Panduan umum untuk user/tim. **Kalau bentrok dengan aturan 1-3, aturan 1-3 yang menang**
(contoh: `git add .`, commit, push, buat branch — semua itu tetap dilakukan user, bukan Claude).

**Alur harian:** sinkron (`git pull`) → buat branch per tugas → commit kecil dan sering →
push branch → buka Pull Request → review + CI lulus → merge → hapus branch.

- **Jangan commit langsung ke `main`.** `main` hanya menerima hasil rilis dari `development`.
  Repo ini dikerjakan sendiri, jadi PR tidak wajib: rilis lewat `release_main.bat`.
- **Satu branch = satu tujuan.** PR kecil lebih mudah di-review.
- Sering `git pull` / merge `main` ke branch kerja supaya tidak tertinggal jauh.
- Jangan pernah commit secret (password, API key, `.env`).
- Hindari `git push --force` ke branch bersama; kalau terpaksa pakai `--force-with-lease`.
- `git stash` kalau perlu pindah branch tapi kerjaan belum siap di-commit.

**Penamaan branch**

| Prefix | Kegunaan |
|---|---|
| `feature/` | Fitur baru |
| `fix/` | Perbaikan bug |
| `hotfix/` | Perbaikan darurat di production |
| `chore/` | Tugas rutin (dependency, config) |
| `docs/` | Dokumentasi |

**Commit:** Conventional Commits (`feat:` / `fix:` / `refactor:` / `docs:` / `chore:`),
bentuk perintah dan jelas — bukan "update", "fix bug", atau "asdf". Sama dengan format
`TITLE` di `commit_session.bat`.

**Release ke `main`:** `main` selalu siap rilis. Tag `vX.Y.Z` harus **sama dengan `APP_VERSION`**.
Alur: `commit_session.bat` (commit + tag di `development`) → `release_main.bat`.

`release_main.bat` mem-*fast-forward* `main` ke `development` lewat
`git push origin development:main` (tanpa `checkout`, tanpa `--force`), lalu push tag.
Syarat: sedang di `development` dan tag versi sudah ada (dari `commit_session.bat`).
Kalau `main` punya commit yang tidak ada di `development`, script me-merge `origin/main` ke
`development` dulu (batal otomatis kalau konflik).

(Kalau suatu saat kerja tim: pakai PR `development` → `main` dengan *merge commit*.)

**Hotfix:** perbaiki di `development` (PATCH baru) → `release_main.bat`. Bila kerja tim: branch
`hotfix/<nama>` dari `main` → PR ke `main` → tag PATCH baru
(mis. `v1.8.1`). Merge juga ke `development` supaya perbaikannya tidak hilang.

**Checklist sebelum rilis**

- [ ] Test/CI lulus
- [ ] `APP_VERSION` sudah dinaikkan, changelog/release notes diperbarui
- [ ] Sudah dicoba di jig/staging
- [ ] Ada rencana rollback (deploy ulang tag sebelumnya)
- [ ] Tag dibuat dari commit yang benar-benar di-deploy

---

## Catatan kondisi repo

- **Branch aktif: `development`** (`origin/HEAD` menunjuk ke `main`). File lama
  `git_commit.bat` melakukan `git push origin main` — jangan dipakai selagi bekerja di
  `development`, karena targetnya salah branch.
- **Line-ending noise:** ratusan file tampil sebagai *modified* tapi isinya identik
  (`git diff --ignore-all-space` kosong). Selama ini belum dibereskan; selalu cek dengan
  `git diff --stat --ignore-all-space` sebelum menganggap sebuah file benar-benar berubah.
  Solusi permanennya menambahkan `.gitattributes` dengan `* text=auto eol=lf`, tapi itu
  perubahan tersendiri yang harus diminta user dulu.
- **`.git/index.lock`** kadang tertinggal dan bikin git menolak menulis. Setiap `.bat`
  yang dibuat harus menghapusnya lebih dulu (sudah ada di template).
