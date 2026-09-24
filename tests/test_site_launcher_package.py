from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "windows" / "site-launcher"


def test_launcher_uses_only_the_canonical_https_site_origin():
    source = (PACKAGE / "ArdorPressureTestLauncher.cs").read_text(encoding="utf-8")
    assert 'SiteUrl = "https://84-247-130-242.sslip.io"' in source
    assert "http://84.247.130.242" not in source


def test_launcher_prefers_edge_then_chrome_and_has_default_browser_fallback():
    source = (PACKAGE / "ArdorPressureTestLauncher.cs").read_text(encoding="utf-8")
    assert source.index('"Microsoft", "Edge"') < source.index('"Google", "Chrome"')
    assert 'Arguments = "--app=' in source
    assert "FileName = SiteUrl" in source
    assert "UseShellExecute = true" in source


def test_launcher_contains_no_credentials_or_session_material():
    source = (PACKAGE / "ArdorPressureTestLauncher.cs").read_text(encoding="utf-8").lower()
    for forbidden in ("password", "authorization", "refresh_token", "access_token", "cookie"):
        assert forbidden not in source


def test_build_script_emits_one_named_windows_executable_and_checksum():
    script = (PACKAGE / "BUILD_SITE_APP.ps1").read_text(encoding="utf-8")
    assert '"ARDOR Pressure Test.exe"' in script
    assert "Microsoft.CSharp.CSharpCodeProvider" in script
    assert 'CompilerOptions = "/target:winexe' in script
    assert ".CompileAssemblyFromFile(" in script
    assert "Get-FileHash" in script
    assert "BUILD_OK: True" in script


def test_build_script_derives_icon_from_existing_ardor_logo():
    script = (PACKAGE / "BUILD_SITE_APP.ps1").read_text(encoding="utf-8")
    assert '"ardor_logo_white.png"' in script
    assert "System.Drawing.Image]::FromFile" in script
    assert "Bitmap.GetHicon()" in script


def test_inno_installer_creates_desktop_shortcut_without_admin_rights():
    installer = (PACKAGE / "installer_setup.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in installer
    assert "DefaultDirName={localappdata}\\Programs\\{#MyAppName}" in installer
    assert 'Name: "{autodesktop}\\{#MyAppName}"' in installer
    assert "ARDOR-Pressure-Test-Setup" in installer
