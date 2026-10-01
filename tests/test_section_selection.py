"""Preserve public section aliases while sharing selection logic across formats."""

import pytest

from exporters.sections import section_selected


@pytest.mark.parametrize("output_format", ["html", "excel"])
def test_default_and_legacy_group_selection(output_format):
    for sections in (None, []):
        assert section_selected(sections, "vpn", output_format)
    for key in ("device_info", "system_settings", "ha", "logging"):
        assert section_selected(["device"], key, output_format)
    assert section_selected(["policy"], "policies", output_format)
    assert section_selected(["policy"], "nat", output_format)
    assert not section_selected(["policy"], "vpn", output_format)
    assert section_selected(["vpn"], "vpn", output_format)


@pytest.mark.parametrize("key", ["interfaces", "routes", "dhcp"])
def test_network_alias_preserves_format_specific_granularity(key):
    assert section_selected([key], "network", "html")
    assert section_selected(["network"], key, "excel")
    other = "routes" if key != "routes" else "interfaces"
    assert not section_selected([key], other, "excel")


def test_retired_selection_does_not_enable_unrelated_sections():
    for output_format in ("html", "excel"):
        assert not section_selected(["cleanup", "analysis_review"], "policies", output_format)
