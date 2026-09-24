$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDirectory "BUILD_SITE_APP.ps1")

$Candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$Compiler = $Candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1

if (-not $Compiler) {
    throw "Inno Setup 6 is required to build the installer. Install it from https://jrsoftware.org/isdl.php and run this script again."
}

$LauncherPath = Join-Path $ScriptDirectory "dist\ARDOR Pressure Test.exe"
$IconPath = Join-Path $ScriptDirectory "ardor-pressure-test.ico"
$OutputDirectory = Join-Path $ScriptDirectory "release"
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

& $Compiler `
    "/DLauncherPath=$LauncherPath" `
    "/DIconPath=$IconPath" `
    "/DOutputDir=$OutputDirectory" `
    (Join-Path $ScriptDirectory "installer_setup.iss")

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE."
}

$SetupPath = Join-Path $OutputDirectory "ARDOR-Pressure-Test-Setup.exe"
if (-not (Test-Path -LiteralPath $SetupPath -PathType Leaf)) {
    throw "The installer was not created."
}

$File = Get-Item -LiteralPath $SetupPath
$Hash = (Get-FileHash -LiteralPath $SetupPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "INSTALLER_BUILD_OK: True"
Write-Host "FILE: $($File.FullName)"
Write-Host "SIZE: $($File.Length) bytes"
Write-Host "SHA256: $Hash"
