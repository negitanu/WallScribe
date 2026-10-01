"""Record structural paths only, never raw values which may contain credentials."""

FORTI_SECTIONS = set(
    """system global|system dns|system ntp|system admin|system interface|system vdom-link|system settings|system ha|system snmp sysinfo|system snmp community|system snmp user|log syslogd setting|log fortianalyzer setting|router static|router static6|router6 static|router ospf|router ospf6|router bgp|router policy|system dhcp server|firewall address|firewall address6|firewall addrgrp|firewall addrgrp6|firewall service custom|firewall service group|firewall policy|firewall security-policy|firewall local-in-policy|firewall vip|firewall ippool|firewall central-snat-map|antivirus profile|webfilter profile|application list|ips sensor|firewall ssl-ssh-profile|vpn ipsec phase1-interface|vpn ipsec phase2-interface|vpn ssl settings""".split(
        "|"
    )
)


def capture_forti_coverage(config, tree):
    for scope, sections in [("global", tree.get("global", {}))] + list(
        tree.get("vdom", {}).items()
    ):
        for section in sections:
            if section != "_name" and section not in FORTI_SECTIONS:
                config.unsupported_sections.append(f"{scope} / {section}")
    for scope, sections in [("global", tree.get("global", {}))] + list(
        tree.get("vdom", {}).items()
    ):
        for section, modeled in FORTI_FIELDS.items():
            for entry in sections.get(section, {}).values():
                if isinstance(entry, dict):
                    for key in entry:
                        if key not in modeled:
                            config.unsupported_sections.append(
                                f"{scope} / {section} / {key} (未モデル化オプション)"
                            )
    # Record fields ignored within modeled sections: these are possible hidden references.
    for scope, sections in [("global", tree.get("global", {}))] + list(
        tree.get("vdom", {}).items()
    ):
        for section in ("system sdwan", "router policy", "vpn ssl settings"):
            if section in sections:
                config.unsupported_sections.append(f"{scope} / {section} (通信評価は未対応)")


def capture_pan_coverage(config, root):
    if root is None:
        return
    # Unknown device/vsys families and external ordered rulebases are review requirements.
    known_device = {"deviceconfig", "network", "vsys"}
    known_vsys = {
        "address",
        "address-group",
        "service",
        "service-group",
        "rulebase",
        "zone",
        "import",
        "profiles",
        "display-name",
        "visible-vsys",
        "application",
        "application-group",
        "application-filter",
    }
    for device in root.findall("./devices/entry"):
        for child in device:
            if child.tag not in known_device:
                config.unsupported_sections.append("devices / " + child.tag)
        for child in device.findall("./network/*"):
            if child.tag not in {
                "interface",
                "profiles",
                "virtual-router",
                "ike",
                "tunnel",
                "global-protect",
            }:
                config.unsupported_sections.append("network / " + child.tag)
        for rulebase in device.findall(".//pre-rulebase") + device.findall(".//post-rulebase"):
            config.unsupported_sections.append("devices / " + rulebase.tag + " (実効順序未解析)")
        for vsys in device.findall("./vsys/entry"):
            for child in vsys:
                if child.tag not in known_vsys:
                    config.unsupported_sections.append(
                        "vsys " + vsys.get("name", "") + " / " + child.tag
                    )
            for child in vsys.findall("./rulebase/*"):
                if child.tag not in {"security", "nat"}:
                    config.unsupported_sections.append("rulebase / " + child.tag)
    for child in root:
        if child.tag not in {"devices", "shared"}:
            config.unsupported_sections.append("config / " + child.tag)
    for child in root.findall("./shared/*"):
        if child.tag not in {
            "address",
            "address-group",
            "service",
            "service-group",
            "profiles",
            "application",
            "application-group",
            "application-filter",
        }:
            config.unsupported_sections.append("shared / " + child.tag)


# Options not represented by the model are surfaced without exposing their values.
FORTI_FIELDS = {
    "firewall address": {
        "_name",
        "uuid",
        "type",
        "subnet",
        "start-ip",
        "end-ip",
        "fqdn",
        "wildcard",
        "comment",
        "tag",
        "tags",
    },
    "firewall address6": {
        "_name",
        "uuid",
        "type",
        "ip6",
        "start-ip",
        "end-ip",
        "fqdn",
        "comment",
        "tag",
        "tags",
    },
    "firewall addrgrp": {"_name", "uuid", "member", "comment", "tag", "tags"},
    "firewall addrgrp6": {"_name", "uuid", "member", "comment", "tag", "tags"},
    "firewall service custom": {
        "_name",
        "protocol",
        "tcp-portrange",
        "udp-portrange",
        "sctp-portrange",
        "icmpcode",
        "icmptype",
        "comment",
        "tag",
        "tags",
    },
    "firewall service group": {"_name", "member", "comment"},
    "router static": {
        "_name",
        "dst",
        "gateway",
        "device",
        "distance",
        "priority",
        "comment",
        "status",
        "blackhole",
    },
}
