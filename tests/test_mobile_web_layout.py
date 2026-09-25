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
