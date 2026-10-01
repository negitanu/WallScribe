"""Selection semantics shared by parameter-sheet exporters.

An empty selection retains the historical meaning of all sections. Network is
one HTML section and three Excel sheets; legacy names map accordingly.
"""

COMMON_ALIASES = {
    "device": frozenset(("device_info", "system_settings", "ha", "logging")),
    "policy": frozenset(("policies", "nat")),
}
FORMAT_ALIASES = {
    "html": {key: frozenset(("network",)) for key in ("interfaces", "routes", "dhcp")},
    "excel": {"network": frozenset(("interfaces", "routes", "dhcp"))},
}


def section_selected(sections, key, output_format):
    if not sections:
        return True
    if key in sections:
        return True
    aliases = FORMAT_ALIASES[output_format]
    return any(
        key in COMMON_ALIASES.get(name, ()) or key in aliases.get(name, ()) for name in sections
    )
