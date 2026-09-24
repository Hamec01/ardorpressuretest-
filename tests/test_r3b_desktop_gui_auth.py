"""Static safety guards for the Tk desktop authentication wiring."""

from pathlib import Path


GUI_SOURCE = Path("src/wika_report/gui.py").read_text()


def _sync_method_source():
    start = GUI_SOURCE.index("    def _start_server_sync(self):")
    end = GUI_SOURCE.index("    def _show_queue_dialog(self):", start)
    return GUI_SOURCE[start:end]


def test_sync_gui_uses_keyring_auth_client_before_constructing_sync_client():
    source = _sync_method_source()
    assert "DesktopAuthClient(base_url=base_url)" in source
    assert source.index("auth_client.get_access_token()") < source.index(
        "SyncClient(base_url=base_url, auth_client=auth_client)"
    )


def test_sync_gui_password_prompt_is_masked_and_password_is_never_written():
    source = _sync_method_source()
    assert 'show="*"' in source
    assert "pending_password" in source
    assert "json.dump" not in source
    assert "write_text" not in source
    assert "logger." not in source


def test_sync_routes_are_deliberately_not_closed_in_this_client_cutover_commit():
    """Server enforcement waits for deployment/distribution verification."""
    source = Path("services/api/routes/sync.py").read_text()
    assert "require_authenticated_user" not in source
