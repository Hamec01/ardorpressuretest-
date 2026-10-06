"""Web checks for admin account management (docs/ACCESS_PLAN_R4-R7.md stage 1)."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "apps" / "web" / "src"


def _read(*parts: str) -> str:
    return WEB.joinpath(*parts).read_text(encoding="utf-8")


def test_accounts_and_set_password_labels_exist_in_all_three_languages():
    i18n = _read("i18n.ts")
    keys = sorted(set(re.findall(r"^    ((?:acc|setpw)_[a-z_]+):", i18n, re.M)) | {"tab_accounts"})
    assert len(keys) > 60
    for key in keys:
        assert i18n.count(f"    {key}:") == 3, key


def test_accounts_tab_is_admin_only():
    app = _read("App.tsx")
    assert "{user?.role === 'admin' && (" in app
    assert "activeTab === 'accounts' && user?.role === 'admin' ? (" in app
    nav = _read("components", "MobileNavigation.tsx")
    assert "{user?.role === 'admin' && <button type=\"button\" className=\"mobile-sheet-row\" onClick={() => selectTab('accounts')}>" in nav


def test_set_password_page_is_public_and_never_sends_cookies():
    main = _read("main.tsx")
    assert "/^\\/set-password\\/([A-Za-z0-9_-]+)\\/?$/" in main
    assert "<SetPasswordPage token={setPasswordMatch[1]} />" in main
    api = _read("api.ts")
    for fn in ("fetchPasswordLink", "submitPasswordLink"):
        body = api[api.index(f"export async function {fn}"):]
        body = body[:body.index("\n}\n")]
        assert "publicFetch(" in body and "authFetch" not in body
    wrapper = _read("authFetch.ts")
    public = wrapper[wrapper.index("export async function publicFetch"):]
    assert "credentials: 'omit'" in public and "Authorization" not in public and "X-CSRF-Token" not in public


def test_admin_cannot_target_own_account_with_dangerous_actions():
    tab = _read("components", "AccountsTab.tsx")
    assert "{!isSelf && <button type=\"button\" className=\"filter-pill\" disabled={busy} onClick={() => setSettingPassword(account)}>" in tab
    assert "{!isSelf && (\n                    <button type=\"button\" className={`filter-pill ${account.is_active ? 'account-danger' : 'account-ok'}`}" in tab
    assert "<RoleSelect value={role} onChange={setRole} disabled={isSelf} />" in tab
