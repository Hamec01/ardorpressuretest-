from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web" / "src"


def read(relative: str) -> str:
    return (WEB / relative).read_text(encoding="utf-8")


def test_mobile_shell_has_five_primary_destinations_and_more_sheet() -> None:
    source = read("components/MobileNavigation.tsx")
    for destination in ("'tests'", "'plans'", "'records'", "'statistics'"):
        assert f"selectTab({destination})" in source
    assert "onOpenFaq();" in source
    assert "mobile_more" in source
    assert 'role="dialog"' in source
    assert 'aria-current=' in source


def test_mobile_shell_reuses_existing_actions_and_contexts() -> None:
    source = read("components/MobileNavigation.tsx")
    assert "onNewTest();" in source
    assert "onLogin();" in source
    assert "onAudit();" in source
    assert "useAuth()" in source
    assert "useI18n()" in source
    assert "useTheme()" in source


def test_mobile_css_covers_phone_tablet_safe_area_and_touch_targets() -> None:
    css = read("index.css")
    assert "@media (max-width: 900px)" in css
    assert "@media (max-width: 480px)" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "env(safe-area-inset-top)" in css
    assert "min-height: 44px" in css
    assert "overflow-x: clip" in css
    assert ".planned-tests-layout" in css
    assert ".modal-content" in css and "100dvh" in css


def test_html_enables_the_real_device_viewport() -> None:
    html = (ROOT / "apps" / "web" / "index.html").read_text(encoding="utf-8")
    assert html.count('name="viewport"') == 1
    assert "width=device-width" in html
    assert "viewport-fit=cover" in html


def test_mobile_labels_exist_in_all_languages() -> None:
    translations = read("i18n.ts")
    for key in (
        "mobile_tests",
        "mobile_plans",
        "mobile_ptr",
        "mobile_faq",
        "mobile_more",
        "mobile_statistics",
        "mobile_language",
        "mobile_trash",
    ):
        assert translations.count(f"{key}:") == 3


def test_statistics_dashboard_is_read_only_and_has_requested_metrics() -> None:
    component = read("components/StatisticsTab.tsx")
    calculation = read("statistics.ts")
    for token in (
        "averagePipesPerActiveDay",
        "averagePressure",
        "topBundleByPipes",
        "topBundleByPressure",
        "bundleDistribution",
        "daily",
    ):
        assert token in component
        assert token in calculation
    forbidden = ("fetch(", "authFetch(", ".commit(", "DELETE FROM", "UPDATE ", "POST ")
    assert all(token not in component and token not in calculation for token in forbidden)


def test_mobile_change_does_not_add_api_or_backend_mutations() -> None:
    source = read("components/MobileNavigation.tsx")
    forbidden = ("fetch(", "authFetch(", "axios", ".commit(", "DELETE FROM", "UPDATE ")
    assert all(token not in source for token in forbidden)


def test_detail_modal_responsive_header_and_close_button_isolated() -> None:
    test_modal = read("components/TestDetailModal.tsx")
    record_modal = read("components/RecordDetailModal.tsx")
    css = read("index.css")

    # Both modals should have structured header top and action container
    assert "test-detail-header" in test_modal
    assert "test-detail-header-top" in test_modal
    assert "test-detail-actions" in test_modal
    assert "test-detail-header-top" in record_modal
    assert "test-detail-actions" in record_modal

    # Close button is in the top bar flow, not absolute floating
    assert 'modal-close-btn"\n          style={{ position: \'absolute\'' not in test_modal
    assert "paddingRight: '3.75rem'" not in test_modal

    # CSS styles exist for both desktop and mobile
    assert ".test-detail-header" in css
    assert ".test-detail-header-top" in css
    assert ".test-detail-actions" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "flex-shrink: 0" in css
    assert ".test-detail-actions > :last-child:nth-child(odd)" in css


def test_share_buttons_create_token_links_through_the_api() -> None:
    """Token share links (docs/ACCESS_PLAN_R4-R7.md stage 2) replace /share/{log_no} URLs."""
    card = read("components/TestCard.tsx")
    detail = read("components/TestDetailModal.tsx")

    assert "await createShare(test.log_no)" in card
    assert "await createShare(currentTest.log_no)" in detail
    assert "{canShare && <button" in card
    for source in (card, detail):
        assert "getPublicShareUrl" not in source
        assert "/share/" not in source
        assert "84.247.130.242" not in source
