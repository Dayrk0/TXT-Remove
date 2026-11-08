$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "assets\app.ico")) {
    throw "缺少 assets\app.ico"
}
if (-not (Test-Path "assets\version_info.txt")) {
    throw "缺少 assets\version_info.txt"
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "小说广告清理工具" `
    --icon "$root\assets\app.ico" `
    --version-file "$root\assets\version_info.txt" `
    --runtime-tmpdir "." `
    --distpath $root `
    --workpath "$root\build\pyinstaller" `
    --specpath "$root\build" `
    "$root\小说广告清理工具.py"

Write-Host "构建完成：$root\小说广告清理工具.exe"
