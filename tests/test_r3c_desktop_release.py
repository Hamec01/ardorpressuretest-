"""Static and executable guards for the R3 authenticated Windows release path."""

import json
import subprocess
import sys
from pathlib import Path

from wika_report import __version__
from wika_report.config import AppConfig, parse_config_dict


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_release_version_is_consistent():
    assert __version__ == "1.1.0"
    assert 'version = "1.1.0"' in (ROOT / "pyproject.toml").read_text()
    assert '#define MyAppVersion "1.1.0"' in (ROOT / "installer_setup.iss").read_text()


def test_module_version_flag_is_non_gui_and_reports_release_version():
    result = subprocess.run(
        [sys.executable, "-m", "wika_report", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip().endswith(__version__)


def test_legacy_config_without_sync_url_gets_safe_verified_default():
    assert parse_config_dict({}).sync_server_url == "https://84-247-130-242.sslip.io"


def test_release_config_points_to_verified_https_origin():
    data = json.loads((ROOT / "config.json").read_text())
    assert parse_config_dict(data).sync_server_url == "https://84-247-130-242.sslip.io"


def test_app_config_exposes_sync_server_url():
    assert AppConfig().sync_server_url.startswith("https://")


def test_windows_requirements_include_desktop_auth_dependencies():
    requirements = (ROOT / "requirements.txt").read_text().splitlines()
    assert "httpx>=0.27.0" in requirements
    assert "keyring>=25.0.0" in requirements


def test_pyinstaller_collects_dynamic_windows_keyring_backends():
    spec = (ROOT / "wika_app.spec").read_text()
    datas, hiddenimports = spec.split("    hiddenimports=", 1)
    assert "collect_submodules(" not in datas
    assert "collect_submodules('keyring.backends')" in hiddenimports
    assert "collect_submodules('win32ctypes')" in hiddenimports


def test_installer_preserves_existing_user_config_on_upgrade():
    installer = (ROOT / "installer_setup.iss").read_text()
    config_line = next(line for line in installer.splitlines() if 'Source: "config.json"' in line)
    assert "onlyifdoesntexist" in config_line


def test_windows_build_script_runs_executable_smoke_check():
    script = (ROOT / "BUILD_APP.bat").read_text()
    assert '"dist\\WIKA CPG1500 Processor.exe" --version' in script
    assert "Built executable smoke test failed" in script


def test_desktop_auth_smoke_never_accepts_password_from_argv_or_environment():
    source = (ROOT / "scripts" / "desktop_auth_smoke.py").read_text()
    assert "getpass.getpass" in source
    assert "sys.stdin.isatty()" in source
    assert "argparse" not in source
    assert "os.environ" not in source
    assert "BUSINESS_SYNC_PERFORMED: False" in source
    assert "client.refresh()" in source


def test_windows_acceptance_document_uses_interactive_non_syncing_smoke():
    document = (ROOT / "docs" / "DESKTOP_R3_WINDOWS_BUILD.md").read_text()
    assert ".venv\\Scripts\\python.exe scripts\\desktop_auth_smoke.py" in document
    assert "BUSINESS_SYNC_PERFORMED: False" in document
