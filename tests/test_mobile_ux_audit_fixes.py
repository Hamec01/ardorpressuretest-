"""Regression checks for the 2026-10-06 mobile audit fixes (ARDOR_Mobile_Audit_2026-10-06/REPORT.md)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web" / "src"


def _read(*parts: str) -> str:
    return WEB.joinpath(*parts).read_text(encoding="utf-8")


def _mobile_css() -> str:
    css = _read("index.css")
    start = css.index("@media (max-width: 900px) {")
    end = css.index("@media (max-width: 480px) {")
    return css[start:end]


def test_full_screen_windows_hide_bottom_nav_and_upload_button_on_phones():
    mobile = _mobile_css()
    assert "body:has(.modal-overlay) .mobile-bottom-nav" in mobile
    assert "body:has(.modal-overlay) .mobile-upload-fab" in mobile
    overlay_z = int(re.search(r"\.modal-overlay \{\s*z-index: (\d+);", mobile).group(1))
    nav_z = int(re.search(r"\.mobile-bottom-nav \{[^}]*z-index: (\d+);", mobile).group(1))
    assert overlay_z > nav_z


def test_list_bottom_padding_leaves_room_for_the_floating_upload_button():
    mobile = _mobile_css()
    padding = re.search(r"\.main-content \{[^}]*padding: 1rem 1rem calc\((\d+)px", mobile)
    assert padding and int(padding.group(1)) >= 150


def test_images_open_in_a_full_screen_viewer_rendered_into_body():
    viewer = _read("components", "ImageViewer.tsx")
    assert "createPortal(" in viewer and "document.body" in viewer
    assert "zoomed" in viewer and "download" in viewer
    detail = _read("components", "TestDetailModal.tsx")
    assert "<ImageViewer" in detail
    assert "zIndex: 1100" not in detail  # the old in-modal lightbox
    css = _read("index.css")
    assert re.search(r"\.image-viewer \{[^}]*position: fixed;[^}]*z-index: 3000;", css)


def test_ptr_seal_wraps_long_codes_and_does_not_repeat_the_role():
    record = _read("components", "RecordDetailModal.tsx")
    seal = record[record.index("record-seal"):record.index("IMMUTABLE OFFICIAL BLANK")]
    assert seal.count("overflowWrap: 'anywhere'") >= 4
    assert "minWidth: 0" in seal
    assert "showSignerRole" in seal
    assert "({record.confirmed_by_role || 'Foreman'})" not in record


def test_ptr_pdf_has_a_phone_fallback_instead_of_an_empty_iframe():
    record = _read("components", "RecordDetailModal.tsx")
    assert 'className="pdf-mobile-fallback"' in record
    assert 'className="pdf-frame"' in record
    mobile = _mobile_css()
    assert ".pdf-frame," in mobile and ".pdf-mobile-fallback {" in mobile


def test_ptr_subtitle_skips_empty_parts():
    record = _read("components", "RecordDetailModal.tsx")
    assert "{record.system} — {record.project}" not in record
    assert ".filter((part) => part && String(part).trim()).join(' — ')" in record


def test_mutating_controls_are_only_shown_to_admin_and_foreman():
    for name in ("TestDetailModal.tsx", "RecordDetailModal.tsx", "RecordsTab.tsx", "PlannedTestsTab.tsx"):
        source = _read("components", name)
        assert "const canEdit = user?.role === 'admin' || user?.role === 'foreman';" in source, name
    detail = _read("components", "TestDetailModal.tsx")
    assert "{canEdit && <button\n                          type=\"button\"\n                          className=\"artifact-action artifact-action-danger\"" in detail
    assert "{canEdit && !isEditing && (" in detail
    plans = _read("components", "PlannedTestsTab.tsx")
    assert "{canEdit && <form onSubmit={handleCreatePlan}" in plans
    app = _read("App.tsx")
    assert "const newTestAction = canEdit ? () => setIsNewTestOpen(true) : user ? undefined : () => setIsLoginOpen(true);" in app


def test_file_actions_are_finger_sized_on_phones():
    mobile = _mobile_css()
    action = re.search(r"\.artifact-action \{([^}]*)\}", mobile).group(1)
    assert "width: 44px;" in action and "height: 44px;" in action


def test_buttons_do_not_get_a_double_plus_or_mixed_language_labels():
    i18n = _read("i18n.ts")
    for key in ("btn_new_test", "btn_create_ptr"):
        for value in re.findall(rf"{key}: '([^']*)'", i18n):
            assert not value.startswith("+"), (key, value)
            assert "(New PTR)" not in value and "(Uusi PTR)" not in value


def test_mobile_audit_labels_exist_in_all_three_languages():
    i18n = _read("i18n.ts")
    keys = (
        "showing_tests", "detail_edit", "share_link", "metrics_title", "metric_test_pressure",
        "graph_title", "graph_expand", "photos_title", "photos_attach", "photo_gauge", "photo_pipe",
        "trace_title", "trace_wika", "files_title", "files_hint", "file_download", "file_copy_sha",
        "file_delete", "viewer_zoom", "viewer_fit", "pdf_mobile_title", "pdf_open", "ptr_unconfirm",
        "login_title", "login_username", "login_password", "login_submit", "card_target",
        "card_duration", "card_share", "ptr_card_medium", "ptr_card_items", "ptr_pdf_blank",
    )
    for key in keys:
        assert i18n.count(f"    {key}:") == 3, key


def test_log_window_and_login_have_no_hardcoded_russian_or_english_labels():
    detail = _read("components", "TestDetailModal.tsx")
    view_mode = detail[detail.index("/* VIEW MODE */"):]
    for text in ("Развернуть", "Прикрепить фото", "Файлы и отчёты ревизии", "Нажмите для открытия",
                 "Inspection & Pressure Metrics", "Traceability & Pipe Identifiers", "Манометр (Gauge)"):
        assert text not in view_mode, text
    header = detail[detail.index('<div className="test-detail-actions">'):detail.index("{/* Body */}")]
    assert "Редактировать данные" not in header and "Ссылка на лог" not in header
    login = _read("components", "LoginModal.tsx")
    for text in ("ARDOR Authentication", ">Username<", ">Password<", "'Sign In'"):
        assert text not in login, text
    assert 'autoComplete="current-password"' in login
    assert "Showing <strong>" not in _read("App.tsx")
