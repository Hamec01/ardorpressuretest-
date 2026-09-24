param(
    [string]$OutputDirectory = ".\dist"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourcePath = Join-Path $ScriptDirectory "ArdorPressureTestLauncher.cs"
$LogoPath = Join-Path $ScriptDirectory "ardor_logo_white.png"
$IconPath = Join-Path $ScriptDirectory "ardor-pressure-test.ico"
$ResolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $ScriptDirectory $OutputDirectory))
$OutputPath = Join-Path $ResolvedOutput "ARDOR Pressure Test.exe"

if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
    throw "Launcher source was not found."
}

if (-not (Test-Path -LiteralPath $LogoPath -PathType Leaf)) {
    throw "ARDOR logo was not found."
}

New-Item -ItemType Directory -Path $ResolvedOutput -Force | Out-Null
Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue

# Build a square Windows icon from the existing ARDOR wordmark. The crop keeps
# the recognizable first letter at desktop-icon sizes without inventing a new logo.
Add-Type -AssemblyName System.Drawing
$Logo = [System.Drawing.Image]::FromFile($LogoPath)
$Bitmap = New-Object System.Drawing.Bitmap 256, 256
$Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
try {
    $Graphics.Clear([System.Drawing.Color]::FromArgb(8, 17, 38))
    $Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $SourceWidth = [Math]::Min([int]($Logo.Width * 0.205), $Logo.Width)
    $SourceRectangle = New-Object System.Drawing.Rectangle 0, 0, $SourceWidth, $Logo.Height
    $DestinationRectangle = New-Object System.Drawing.Rectangle 53, 16, 150, 224
    $Graphics.DrawImage($Logo, $DestinationRectangle, $SourceRectangle, [System.Drawing.GraphicsUnit]::Pixel)
    $IconHandle = $Bitmap.GetHicon()
    $Icon = [System.Drawing.Icon]::FromHandle($IconHandle)
    $IconStream = [System.IO.File]::Create($IconPath)
    try {
        $Icon.Save($IconStream)
    }
    finally {
        $IconStream.Dispose()
        $Icon.Dispose()
    }
}
finally {
    $Graphics.Dispose()
    $Bitmap.Dispose()
    $Logo.Dispose()
}

$Provider = New-Object Microsoft.CSharp.CSharpCodeProvider
$CompilerParameters = New-Object System.CodeDom.Compiler.CompilerParameters
$CompilerParameters.GenerateExecutable = $true
$CompilerParameters.GenerateInMemory = $false
$CompilerParameters.OutputAssembly = $OutputPath
$CompilerParameters.CompilerOptions = "/target:winexe /optimize+ /win32icon:`"$IconPath`""
[void]$CompilerParameters.ReferencedAssemblies.Add("System.dll")

$Compilation = $Provider.CompileAssemblyFromFile($CompilerParameters, $SourcePath)
if ($Compilation.Errors.HasErrors) {
    $Messages = $Compilation.Errors | ForEach-Object {
        "line $($_.Line): $($_.ErrorNumber) $($_.ErrorText)"
    }
    throw "C# compilation failed:`n$($Messages -join [Environment]::NewLine)"
}

if (-not (Test-Path -LiteralPath $OutputPath -PathType Leaf)) {
    throw "The Windows executable was not created."
}

$File = Get-Item -LiteralPath $OutputPath
$Hash = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()

Write-Host "BUILD_OK: True"
Write-Host "FILE: $($File.FullName)"
Write-Host "SIZE: $($File.Length) bytes"
Write-Host "SHA256: $Hash"
