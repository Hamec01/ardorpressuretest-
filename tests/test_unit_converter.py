import pytest
from wika_report.unit_converter import convert_value_to_bar, get_conversion_factor, is_supported_unit, normalize_unit_name


def test_unit_normalization():
    assert normalize_unit_name("Pressure / bar") == "bar"
    assert normalize_unit_name("PSI") == "psi"
    assert normalize_unit_name("kPa") == "kpa"
    assert normalize_unit_name("бар") == "bar"


def test_conversions():
    assert pytest.approx(convert_value_to_bar(100.0, "kPa"), 0.001) == 1.0
    assert pytest.approx(convert_value_to_bar(1.0, "MPa"), 0.001) == 10.0
    assert pytest.approx(convert_value_to_bar(100000.0, "Pa"), 0.001) == 1.0
    assert pytest.approx(convert_value_to_bar(14.50377, "psi"), 0.01) == 1.0
    assert pytest.approx(convert_value_to_bar(1.0, "bar"), 0.001) == 1.0


def test_unsupported_unit():
    assert not is_supported_unit("unknown_unit")
    with pytest.raises(ValueError, match="Неизвестная или неподдерживаемая единица"):
        get_conversion_factor("unknown_unit")
